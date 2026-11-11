# Laboratorio 10 — Clase 14 (Vie 13-nov): NiFi, del CSV a Postgres y Redis, y romperlo a propósito

> La teoría de NiFi la vimos el martes 10-nov (online). Hoy se arma el flujo en el canvas, en las máquinas del laboratorio. **No hay notebook:** el «notebook» es el canvas de NiFi en el navegador, y este README es la receta, diapositiva por diapositiva. Después de cada paso, `python3 checkpoint.py` les dice si Postgres y Redis quedaron como deben. Material de estudio: [`CONTENTS.md`](CONTENTS.md) (léanlo si nunca han usado NiFi: explica cada pieza y cada propiedad).

*Libreto: `Clases/Clase 14 (1311)/Clase 14 (1311) — Libreto.md` · guía docente: `Clases/Clase 14 (1311)/Clase 14 (1311) — Laboratorio 10.md` (en la carpeta del curso, fuera de este repositorio).*

Primera clase del bloque ETL. En la C12 cargamos un CSV con `LOAD CSV` + `MERGE`, **a mano**. Hoy la pregunta es otra: ¿quién hace esa carga cuando el archivo llega solo, cada hora? ¿Qué pasa si la base está caída? ¿Y si el mismo archivo llega dos veces? Usamos los mismos 16 sensores de los Labs 06–07 (el mismo `generador.py`) y, en el bonus, el grafo de paradas de los Labs 08–09.

## Qué se necesita

- **Docker** con `docker compose` y ~3 GB de RAM libre.
- Las imágenes, descargadas **antes** de clase (el viernes no se descarga nada):

  ```bash
  docker compose pull                    # NiFi, Postgres y Redis: ~1,3 GB de descarga, ~3,3 GB en disco
  docker compose --profile bonus pull    # además Neo4j, para el bonus: ~340 MB más (~1 GB en disco)
  ```

- Los datos y el driver de Postgres, una vez:

  ```bash
  python3 preparar_datos.py
  ```

  Tiene que terminar con `Verificación OK: 6 archivos · 43.200 filas · 42.368 claves únicas → pendientes/`. Deja seis CSV en `pendientes/` y el JAR `postgresql-42.7.14.jar` en `drivers/`. Si no hay red, avisa y sigue: copien el JAR del pendrive a `drivers/`.

No hace falta ningún paquete de Python: `preparar_datos.py` y `checkpoint.py` usan solo la biblioteca estándar.

> ⚠️ **Bajen los contenedores de otros labs antes de levantar este.** Este lab usa los mismos nombres: `pmd-postgis` (Labs 01–05), `pmd-redis` (Lab 06) y `pmd-neo4j` (Labs 08–09). Si alguno existe, `docker compose up` falla con *container name "/pmd-postgis" is already in use*. En estas máquinas no hay nada que perder:
>
> ```bash
> docker rm -f pmd-postgis pmd-redis pmd-neo4j
> ```

## El stack

```bash
docker compose up -d --wait            # levantar y esperar a que NiFi responda (1-3 min)
open https://localhost:8443/nifi       # Windows/Linux: ábranlo en el navegador
docker compose --profile bonus down -v # al terminar: apagar todo y borrar los volúmenes
```

| Servicio | Contenedor | Puerto en su máquina | Para qué | Cómo lo nombra NiFi |
|---|---|---|---|---|
| NiFi 2.12.0 | `pmd-nifi` | `8443` | el canvas: <https://localhost:8443/nifi> | — |
| Postgres 16 | `pmd-postgis` | `5433` | la tabla `eventos`, la historia completa | `postgres:5432` |
| Redis 7 | `pmd-redis` | `6379` | `sensor:<id>`, el estado actual de cada sensor | `redis:6379` |
| Neo4j 5 (bonus) | `pmd-neo4j` | `7474`, `7687` | el grafo de paradas del Lab 09 + los sensores | `neo4j:7474` |

Los cuatro están en la misma red de Docker: NiFi les habla **por el nombre del servicio**. Dentro del contenedor de NiFi, `localhost` es el propio NiFi, no su máquina.

NiFi ve tres carpetas de su máquina, montadas adentro. **En las propiedades de NiFi siempre va la ruta de adentro.**

| Afuera (su máquina) | Adentro (NiFi) | Qué hay |
|---|---|---|
| `./entrada/` | `/data/entrada` | aquí «llegan» los archivos: NiFi los mira cada 5 s |
| `./errores/` | `/data/errores` | la cola de descarte: lo que no se pudo cargar |
| `./drivers/` | `/opt/nifi/drivers` | el JAR de PostgreSQL JDBC |

**Usuario `admin`, clave `pmd2026pmd2026`.** NiFi exige 12 caracteres o más: con menos, inventa otros y los deja en el log (`docker compose logs nifi | grep Generated`).

**El certificado.** NiFi trae un certificado autofirmado, así que el navegador va a reclamar. Chrome: *Configuración avanzada* y después el enlace para continuar a `localhost`; si no aparece la opción, hagan clic en la página y escriban `thisisunsafe` (no se ve nada mientras escriben). Firefox: *Avanzado → Aceptar el riesgo y continuar*.

## Los datos

Seis horas de los 16 sensores del 13-nov (08:00 a 13:59), un archivo por hora, en el **orden en que llegaron**. Salen de `eventos()` del Lab 06, con la misma semilla. Cabecera `estacion_id,tipo_sensor,valor,ts`; `valor` siempre con un decimal (`80.0`, no `80`); `ts` con milisegundos y zona horaria (`2026-11-13T08:00:01.000-03:00`).

| Archivo | Filas | Repetidas | Únicas `(estacion_id, ts)` | `calidad_aire` > 70 |
|---|---|---|---|---|
| `eventos_0800.csv` | 7.200 | 137 | 7.063 | 607 |
| `eventos_0900.csv` | 7.200 | 163 | 7.037 | 570 |
| `eventos_1000.csv` | 7.200 | 138 | 7.062 | 644 |
| `eventos_1100.csv` | 7.200 | 126 | 7.074 | 544 |
| `eventos_1200.csv` | 7.200 | 126 | 7.074 | 624 |
| `eventos_1300.csv` | 7.200 | 142 | 7.058 | 561 |

Las repetidas son el 2 % de reenvíos del generador (Lab 06): copias exactas de la fila anterior, con la misma clave. Entre archivos no se repite ninguna clave.

Los archivos esperan en `pendientes/`. **Copiar un archivo a `entrada/` es simular que llegó.** NiFi no sabe de dónde vino: solo ve que apareció un archivo nuevo en su carpeta.

## La receta

Todo se arma dentro de un **Process Group** llamado `Lab 10`: arrastren el ícono de Process Group (la barra de arriba) al canvas, pónganle el nombre y hagan doble clic para entrar. Los controller services y los procesadores van adentro.

Dos reglas que se aplican a todos los pasos:

- **Cada relación de un procesador se conecta o se termina.** Si una queda suelta, el procesador muestra un triángulo amarillo y no arranca. Para terminarla: *Configure → Relationships*, casilla **terminate**.
- **Los comandos de terminal se escriben en `Laboratorios/10/`**, en su máquina (no dentro de un contenedor).

### Diapositiva 5 — Levantar el stack

```bash
docker compose up -d --wait
```

Abran <https://localhost:8443/nifi>, acepten el certificado y entren con `admin` / `pmd2026pmd2026`.

**Resultado esperado:** `docker compose ps` muestra los tres servicios `healthy` y el navegador muestra el canvas vacío.

### Diapositiva 6 — Tour del canvas

Arrastren el ícono de **Processor** (el primero de la barra de arriba) al canvas. Se abre un diálogo con un buscador (*Filter types*): escriban `GenerateFlowFile`, selecciónenlo y hagan clic en *Add*. Clic derecho sobre la caja → *Configure*: miren las pestañas *Settings*, *Scheduling*, *Properties* y *Relationships*, y cierren sin cambiar nada. Pasen el mouse por el triángulo amarillo: dice qué falta.

### Diapositiva 7 — Primer flujo: abrir un FlowFile

| Procesador | Pestaña | Propiedad | Valor |
|---|---|---|---|
| `GenerateFlowFile` | Properties | Custom Text | `hola Concepción` |
| | Scheduling | Run Schedule | `5 sec` |
| `LogAttribute` | Relationships | `success` | **terminate** (desde que se crea) |

1. Arrastren la flecha desde `GenerateFlowFile` hasta `LogAttribute` (aparece al pasar el mouse por el centro de la caja) y elijan `success`.
2. Inicien **solo** `GenerateFlowFile` (clic derecho → *Start*). La cola sube: 1, 2, 3…
3. Clic derecho sobre la cola → *List Queue*. En el menú de un FlowFile: *View details* muestra sus **atributos** (*Attribute Values*) y *View content*, su **contenido**.
4. Inicien `LogAttribute`: la cola se vacía.
5. Detengan los dos y bórrenlos (seleccionar + Supr): el canvas queda limpio para lo que sigue.

> 🤔 **Antes de ejecutar:** ¿por qué el `uuid` es distinto en cada FlowFile si el contenido es idéntico?

**Resultado esperado:** la cola con FlowFiles visibles y uno abierto, con `uuid`, `filename` y `entryDate` en sus atributos.

### Diapositiva 8 — Los archivos llegan: `ListFile` → `FetchFile`

| Procesador | Pestaña | Propiedad | Valor |
|---|---|---|---|
| `ListFile` | Properties | Input Directory | `/data/entrada` |
| | Properties | File Filter | `eventos_.*\.csv` |
| | Scheduling | Run Schedule | `5 sec` (por defecto mira cada 1 min) |
| `FetchFile` | Properties | (todo por defecto: File to Fetch = `${absolute.path}/${filename}`, Completion Strategy = `None`) | |
| | Relationships | `not.found`, `permission.denied`, `failure` | **terminate** (el archivo sigue en `entrada/`) |
| `LogAttribute` (provisorio) | Relationships | `success` | **terminate** |

Conecten `ListFile → FetchFile` (`success`) y `FetchFile → LogAttribute` (`success`). Inicien `ListFile` y `FetchFile`; **dejen detenido** el `LogAttribute`. Ahora llega el primer archivo:

```bash
cp pendientes/eventos_0800.csv entrada/
```

Abran el FlowFile de la cola hacia el `LogAttribute`: miren `filename`, `absolute.path` y `file.size`.

> 🤔 **Antes de ejecutar:** ¿cuántos FlowFiles van a aparecer en la cola: uno o 7.200?

**Resultado esperado:** 1 FlowFile de ~424 KB en la cola hacia el `LogAttribute`, con `filename` = `eventos_0800.csv`.

### Diapositiva 9 — Los *controller services*

Clic derecho en un espacio vacío del canvas (dentro de `Lab 10`) → *Controller Services* → **+**. Creen dos por ahora:

| Servicio | Propiedad | Valor |
|---|---|---|
| `CSVReader` | Schema Access Strategy | `Infer Schema` |
| | Treat First Line as Header | `true` |
| `DBCPConnectionPool` | Database Connection URL | `jdbc:postgresql://postgres:5432/postgres?stringtype=unspecified` |
| | Database Driver Class Name | `org.postgresql.Driver` |
| | Database Driver Locations | `/opt/nifi/drivers/postgresql-42.7.14.jar` (nombre exacto: `ls drivers/`) |
| | Database User | `postgres` |
| | Password | `pmd2026` |
| | Validation Query | `SELECT 1` |

Cada servicio se configura con el ícono de engranaje de su fila y se **habilita** con el rayo (*Enable*). Deshabilitado, ningún procesador que lo use puede arrancar.

Dos detalles de la URL: el host es `postgres` (el nombre del servicio, no `localhost`), y `?stringtype=unspecified` le dice al driver que deje a Postgres convertir el texto de `ts` a `timestamptz`. Sin eso, la carga falla (ver *Problemas comunes*). `SELECT 1` sirve para que, cuando Postgres vuelva de una caída, el pool descarte las conexiones muertas antes de usarlas.

**Resultado esperado:** los dos servicios en `Enabled`, sin triángulos.

### Diapositiva 10 — Destino 1: Postgres, sin duplicar

| Procesador | Pestaña | Propiedad | Valor |
|---|---|---|---|
| `PutDatabaseRecord` | Properties | Record Reader | `CSVReader` |
| | Properties | Database Type | `PostgreSQL` |
| | Properties | Statement Type | `INSERT_IGNORE` |
| | Properties | Database Connection Pooling Service | `DBCPConnectionPool` |
| | Properties | Table Name | `eventos` |
| | Relationships | `success` | **terminate** |
| `PutFile` | Properties | Directory | `/data/errores` |
| | Properties | Conflict Resolution Strategy | `replace` |
| | Relationships | `success`, `failure` | **terminate** |

`PutDatabaseRecord` tiene **tres** salidas: `success`, `failure` y `retry` («no se pudo, pero un intento posterior puede funcionar»). Las tres tienen que quedar resueltas: `success` se termina, y `failure` **y** `retry` van, en una misma connection, a `PutFile`.

El archivo de las 08:00 está esperando en la cola del `LogAttribute` provisorio. Para cambiar el destino hay que sacar esa connection, y una connection con FlowFiles no se puede borrar:

1. Clic derecho en la cola `FetchFile → LogAttribute` → *Empty Queue*. El FlowFile se descarta.
2. Detengan `FetchFile`, borren la connection y el `LogAttribute`.
3. Conecten `FetchFile → PutDatabaseRecord` (`success`) y `PutDatabaseRecord → PutFile` (`failure` y `retry`).
4. Inicien `PutFile`, `PutDatabaseRecord` y `FetchFile`.
5. El archivo de las 08:00 se perdió en el paso 1. Vuelvan a copiarlo: `cp` le cambia la fecha de modificación y `ListFile` lo ve como nuevo.

```bash
cp pendientes/eventos_0800.csv entrada/
docker exec pmd-postgis psql -U postgres -c "SELECT count(*) FROM eventos;"
python3 checkpoint.py
```

La tabla ya existe: la creó el compose con `sql/01_tablas.sql`, con `PRIMARY KEY (estacion_id, ts)`. `INSERT_IGNORE` es `INSERT … ON CONFLICT DO NOTHING`: si la clave ya está, la fila se salta.

> 🤔 **Antes de ejecutar:** el archivo tiene 7.200 filas. ¿Cuántas van a quedar en la tabla?

**Resultado esperado:** `count = 7063` · `✓ Calza con: después de la diapositiva 10`.

### Diapositiva 11 — Destino 2: Redis, el estado actual de cada sensor

Agreguen tres servicios más (*Controller Services* → **+**) y habilítenlos:

| Servicio | Propiedad | Valor |
|---|---|---|
| `JsonRecordSetWriter` | (todo por defecto) | |
| `JsonTreeReader` | Schema Access Strategy | `Infer Schema` |
| `RedisConnectionPoolService` | Redis Mode | `Standalone` |
| | Connection String | `redis:6379` |

Y dos procesadores:

| Procesador | Pestaña | Propiedad | Valor |
|---|---|---|---|
| `QueryRecord` | Properties | Record Reader | `CSVReader` |
| | Properties | Record Writer | `JsonRecordSetWriter` |
| | Properties | **+** propiedad nueva `estado` | la consulta de abajo |
| | Relationships | `original`, `failure` | **terminate** |
| `PutRedisHashRecord` | Properties | Record Reader | `JsonTreeReader` |
| | Properties | Redis Connection Pool | `RedisConnectionPoolService` |
| | Properties | Hash Value Record Path | `/clave` |
| | Properties | Data Record Path | `/` (por defecto) |
| | Relationships | `success`, `failure` | **terminate** |

```sql
SELECT 'sensor:' || estacion_id AS clave, estacion_id, tipo_sensor, valor, ts
FROM FLOWFILE
```

1. **Detengan `FetchFile`** y arrastren una **segunda** connection desde `FetchFile` (`success`) hasta `QueryRecord`. El mismo FlowFile viaja ahora por las dos ramas. NiFi deja agregarla con `FetchFile` corriendo, pero detenerlo antes de tocar sus salidas es la buena práctica. Vuelvan a iniciarlo.
2. La propiedad nueva se agrega con el **+** de la pestaña *Properties* (*Add Property*). **Cada propiedad nueva de `QueryRecord` es una relación de salida** con ese nombre: conecten `QueryRecord → PutRedisHashRecord` con la relación `estado`.
3. Inicien `PutRedisHashRecord` y `QueryRecord`. Llega la hora siguiente:

```bash
cp pendientes/eventos_0900.csv entrada/
docker exec pmd-redis redis-cli HGETALL sensor:CC-004
docker exec pmd-redis redis-cli DBSIZE
python3 checkpoint.py
```

`FLOWFILE` es el nombre de la «tabla» dentro de `QueryRecord`: el SQL corre sobre las filas del FlowFile. Cada fila hace un `HSET` sobre su clave, así que la última fila de cada sensor queda como su estado actual.

> 🤔 **Antes de ejecutar:** esta rama no deduplica. ¿Le importa a Redis recibir dos veces la misma fila?

**Resultado esperado:** Postgres = **14.100** · `DBSIZE` = **16** · `HGETALL sensor:CC-004`:

```
clave        sensor:CC-004
estacion_id  CC-004
tipo_sensor  calidad_aire
valor        69.8
ts           2026-11-13T09:59:53.500-03:00
```

(`redis-cli` lo muestra en líneas alternadas: nombre del campo, valor.) El campo `clave` también queda en el hash: `PutRedisHashRecord` escribe todos los campos del registro.

**Si terminan antes:** en el mismo `QueryRecord`, una propiedad `alertas` con `SELECT * FROM FLOWFILE WHERE tipo_sensor = 'calidad_aire' AND valor > 70`, conectada a un `LogAttribute` con `success` en *terminate*. Copien la hora siguiente y miren el atributo `record.count` del FlowFile que pasa por `alertas` (*List Queue* con el `LogAttribute` detenido, o *View Data Provenance*): es la última columna de la tabla de los datos. Para el archivo de las 09:00 dice **570**.

### Diapositiva 12 — Romperlo a propósito: Postgres se cae

Primero, dos cambios (con `PutDatabaseRecord` detenido):

| Dónde | Qué | Valor |
|---|---|---|
| `PutDatabaseRecord` → *Configure* → *Relationships* | casilla **retry** en `failure` **y** en `retry` | |
| | Number of Retry Attempts | `10` |
| | Retry Back Off Policy | `Penalize` |
| | Retry Maximum Back Off Period | `30 sec` |
| connection `FetchFile → PutDatabaseRecord` → *Configure* | Back Pressure Object Threshold | `1` (por defecto, 10.000 objetos o 1 GB) |

Vuelvan a iniciar `PutDatabaseRecord`. Ahora botamos Postgres y llegan tres horas, **de a una**:

```bash
docker stop pmd-postgis
for h in 1000 1100 1200; do cp pendientes/eventos_$h.csv entrada/; sleep 6; done
python3 checkpoint.py           # Postgres caído: el checkpoint lo dice y revisa solo Redis
```

Miren el canvas 1–2 minutos: el cuadrito rojo (*bulletin*) en `PutDatabaseRecord`, la cola `FetchFile → PutDatabaseRecord` en **1/1** y en rojo, y la cola `ListFile → FetchFile` con **2**. Después:

```bash
docker start pmd-postgis
python3 checkpoint.py           # esperen ~30 s a que el reintento vuelva a probar
```

> 🤔 **Antes de levantar Postgres:** ¿la rama de Redis siguió recibiendo datos con Postgres caído? Y cuando vuelva, ¿qué cola se vacía primero?

**Resultado esperado, con Postgres caído:** `sensor:CC-004` → `valor` 77.3, `ts` …10:59:57.500 · `✓ Calza con: … con Postgres caído`.
**Con Postgres de vuelta:** Postgres = **35.310** · `sensor:CC-004` → `valor` **80.0**, `ts` …12:59:55.500 · nada en `errores/`.

¿Por qué de a uno con `sleep 6`? Si copian los tres en un solo `cp`, NiFi no promete en qué orden los procesa, y Redis podría terminar con 69.7 (11:00) en vez de 80.0 (12:00). Postgres queda igual en los dos casos.

### Diapositiva 13 — Reenviar un archivo viejo: Postgres resiste, Redis retrocede

Alguien reenvía el archivo de las 08:00:

```bash
cp pendientes/eventos_0800.csv entrada/
docker exec pmd-postgis psql -U postgres -c "SELECT count(*) FROM eventos;"
docker exec pmd-redis redis-cli HGET sensor:CC-004 valor
python3 checkpoint.py
```

> 🤔 **Antes de ejecutar:** ¿Postgres sube a 42.373 o se queda en 35.310? ¿Y Redis?

**Resultado esperado:** Postgres = **35.310** · `sensor:CC-004` → `valor` **64.2**, `ts` …08:59:47.000.

Después, **Data Provenance**: clic derecho en `PutDatabaseRecord` → *View Data Provenance*. Cada fila es un evento de un FlowFile (cuándo, qué tipo, con qué atributos). En el menú de una fila: *View Details* (los atributos y el contenido) y *Show Lineage* (la historia del FlowFile, de `ListFile` a su destino). El botón *Replay* vuelve a mandar ese FlowFile.

## Checkpoint

`python3 checkpoint.py` compara lo que ve con esta tabla:

| Después de… | Postgres | Redis `DBSIZE` | `sensor:CC-004` valor | `errores/` |
|---|---|---|---|---|
| Diap. 10 · `0800` (copiado de nuevo) | 7.063 | 0 | — | 0 |
| Diap. 11 · `0900` | 14.100 | 16 | 69.8 | 0 |
| Diap. 12 · Postgres caído, tras los tres `cp` | (caído) | 16 | 77.3 | 0 |
| Diap. 12 · Postgres de vuelta | 35.310 | 16 | 80.0 | 0 |
| Diap. 13 · reenvío de `0800` | 35.310 | 16 | 64.2 | 0 |
| Bonus · `1300` | 42.368 | 16 | 70.3 | 0 |

## Si se atrasan: el flujo de rescate

`rescate/flujo_lab10.json` es el flujo terminado de las diapositivas 8–12, con `alertas`, los reintentos y el umbral 1 ya puestos. Para usarlo:

1. Si ya tienen un `Lab 10` a medias, bórrenlo o déjenlo detenido al lado.
2. Arrastren el ícono de **Process Group** al canvas. En el diálogo *Create Process Group*, el ícono **Browse** (a la derecha del campo *Name*) sube un archivo: elijan `rescate/flujo_lab10.json` y hagan clic en *Add*.
3. Entren al grupo → *Controller Services*. En `DBCPConnectionPool` escriban la clave `pmd2026` en *Password*: NiFi **no exporta** las claves.
4. Habiliten los cinco servicios y, con clic derecho en el canvas, *Start*.

Desde ahí pueden seguir en cualquier diapositiva. Si Postgres ya tiene filas, `INSERT_IGNORE` las respeta. `ListFile` parte de cero: va a listar todo lo que haya en `entrada/`.

## Bonus: Neo4j

NiFi 2 ya no trae procesadores de Neo4j, así que esta rama le habla a la API HTTP de Neo4j con `InvokeHTTP`. Parte del grafo base del Lab 09 (12 paradas, 7 comunas) en un volumen propio.

```bash
docker compose --profile bonus up -d --wait
docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo < bonus/01_cargar_grafo.cypher
```

En el mismo `QueryRecord` (detenido), una propiedad más:

| Propiedad | Valor |
|---|---|
| `resumen` | `SELECT estacion_id, tipo_sensor, COUNT(*) AS n, AVG(valor) AS promedio, MAX(ts) AS ultimo_ts FROM FLOWFILE GROUP BY estacion_id, tipo_sensor` |

| Procesador | Propiedad | Valor | Relaciones |
|---|---|---|---|
| `ReplaceText` | Replacement Strategy | `Surround` | `resumen` de `QueryRecord` entra aquí · `success` → `InvokeHTTP` · `failure` → `PutFile` |
| | Evaluation Mode | `Entire text` | |
| | Text to Prepend / Text to Append | los dos textos de `plantillas/neo4j_surround.txt` | |
| `InvokeHTTP` | HTTP Method | `POST` | `Response` → `LogAttribute` · `Original` → **terminate** · `Failure`, `No Retry`, `Retry` → `PutFile` |
| | HTTP URL | `http://neo4j:7474/db/neo4j/tx/commit` | |
| | Request Username / Request Password | `neo4j` / `pmd2026neo` | |
| | Request Content-Type | `application/json` | |
| `LogAttribute` | Log Payload | `true` (para ver la respuesta de Neo4j) | `success` → **terminate** |

Inicien todo y copien la última hora:

```bash
cp pendientes/eventos_1300.csv entrada/
python3 checkpoint.py --bonus
```

Ojo: la API de Neo4j responde **200 aunque la consulta falle**, con el error dentro del JSON, en `errors`. Revisen la respuesta en el log del `LogAttribute`: tiene que decir `"errors":[]`.

```bash
docker compose logs nifi | grep '"errors"'
```

La consulta que cruza las dos familias de bases (en `cypher-shell` o en <http://localhost:7474>):

```cypher
MATCH (s:Sensor {tipo: 'calidad_aire'})-[:EN]->(c:Comuna)<-[:EN]-(p:Parada)
WHERE s.promedio > 60
RETURN c.nombre AS comuna, collect(p.nombre) AS paradas;
```

**Resultado esperado:** Postgres = **42.368** · 16 nodos `Sensor` con 16 relaciones `EN` · `CC-004` con `n` = 464 y `promedio` ≈ 73.84 · la consulta, **3 filas**: Concepción (4 paradas), Talcahuano (2) y Chiguayante (1). Coronel queda fuera: su sensor de aire promedia 35.01.

## Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| El navegador dice *connection refused* | NiFi todavía no termina de arrancar: `docker compose ps` hasta que diga `healthy`, o `docker compose logs -f nifi` hasta `Started Application`. |
| *container name … already in use* | Un contenedor de otro lab: `docker rm -f pmd-postgis pmd-redis pmd-neo4j`. |
| Triángulo amarillo: *Relationship X is invalid because…* | Una relación sin conectar ni terminar. Pasa con `retry` de `PutDatabaseRecord`, `original` de `QueryRecord` y `success` de `LogAttribute` y `PutFile`. |
| El procesador no arranca y dice que un servicio está deshabilitado | *Controller Services*: los cinco tienen que decir `Enabled`. |
| `DBCPConnectionPool` no habilita | La ruta del JAR: `/opt/nifi/drivers/` + el nombre exacto que muestra `ls drivers/`. |
| Todo sale a `errores/` y el bulletin dice *column "ts" is of type timestamp with time zone but expression is of type character varying* | Falta `?stringtype=unspecified` al final de la *Database Connection URL*. NiFi infiere `ts` como texto. |
| `ListFile` no ve el archivo | *Input Directory* = `/data/entrada` (la ruta de adentro) y *File Filter*. Para que vuelva a ver un archivo ya listado: `cp` de nuevo, o *View State → Clear state*. |
| Se perdió el archivo de las 08:00 al borrar el `LogAttribute` provisorio | Es lo esperado (*Empty Queue* lo descarta): `cp` otra vez. |
| Con Postgres caído, la cola hacia `PutDatabaseRecord` no se llena | Falta la casilla **retry** en `failure` y `retry` (el FlowFile se fue directo a `errores/`). Si ya está en `errores/`, con Postgres arriba: `cp errores/eventos_*.csv entrada/`. |
| Redis quedó en 69.7 y no en 80.0 | Copiaron los tres archivos en un solo `cp`: NiFi no promete orden. Postgres queda igual. |
| Después de `docker start`, sigue fallando un rato | El reintento espera hasta 30 s entre intentos. Esperen. |
| El bonus no escribe nada en Neo4j | El error está en `errors`, dentro de la respuesta: mírenlo en el `LogAttribute` (*Log Payload* = `true`). |
| La máquina se arrastra | `docker stats`. NiFi usa hasta 1 GB de heap; no levanten el bonus si falta memoria. |

## Al terminar

```bash
docker compose --profile bonus down -v
```

Apaga todo y borra los volúmenes (`pmd10-pgdata`, `pmd10-neo4jdata` y los de NiFi). Las máquinas son compartidas. Para repetir el lab desde cero, vacíen también `entrada/` y `errores/` (`rm entrada/*.csv errores/*.csv`).

## Archivos

| Archivo | Qué es |
|---|---|
| `README.md` | esta receta |
| `CONTENTS.md` | material de estudio: NiFi para quien nunca lo ha usado |
| `docker-compose.yml` | NiFi + Postgres + Redis, y Neo4j con el perfil `bonus` |
| `preparar_datos.py` | escribe los seis CSV en `pendientes/` (con `../06/generador.py`) y baja el JAR a `drivers/` |
| `checkpoint.py` | dice en qué paso calzan Postgres y Redis (`--bonus`: también Neo4j) |
| `sql/01_tablas.sql` | la tabla `eventos`, con `PRIMARY KEY (estacion_id, ts)`; la crea el compose |
| `plantillas/neo4j_surround.txt` | los dos textos del `ReplaceText` del bonus |
| `bonus/01_cargar_grafo.cypher` | el grafo base de los Labs 08–09 |
| `rescate/flujo_lab10.json` | el flujo terminado, para importarlo si se atrasan (sin claves) |
| `entrada/` | aquí «llegan» los archivos (vacía al empezar) |
| `pendientes/` | los seis CSV que deja `preparar_datos.py` (no se versionan) |
| `errores/` | la cola de descarte: lo que `PutFile` escribe cuando algo falla |
| `drivers/` | el JAR de PostgreSQL JDBC (no se versiona) |
