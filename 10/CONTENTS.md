# Contenidos — NiFi: mover datos sin escribir un script por cada flecha

**Curso:** Procesamiento Masivo de Datos (ELE051-B / EIN102B) · Paralelo 701 · 2026-2
**Bloque ETL (1 de 2) · Material de estudio del Laboratorio 10 · noviembre de 2026**

> Material de estudio del Laboratorio 10, para quien **nunca ha usado NiFi**. Primero el modelo mental, después el canvas pieza por pieza y al final cada procesador y cada propiedad del lab. La receta paso a paso está en el [`README.md`](README.md); aquí está el porqué. Todo lo que aparece aquí salió de armar el flujo del lab contra NiFi 2.12.0, con los mismos datos: los nombres de menús, propiedades y mensajes son los que muestra esa versión.

---

## 1. Qué es NiFi y qué problema resuelve

En la C12 cargamos un CSV en Neo4j con `LOAD CSV` + `MERGE`. Funcionó, pero lo ejecutamos **nosotros, a mano, una vez**. En un sistema real los archivos llegan solos y la pregunta cambia: ¿quién ejecuta la carga? Tres preguntas concretas:

| Pregunta | Lo que tendría que programar un script con `cron` | Lo que trae NiFi |
|---|---|---|
| Llega un archivo nuevo **cada hora**. ¿Quién lo carga? | Revisar la carpeta cada cierto tiempo y recordar qué archivos ya procesó (en un archivo o una tabla aparte) | `ListFile` revisa la carpeta y guarda lo que ya listó en su *state* |
| A las 11:00 la base está **caída**. ¿Se pierde esa hora? | Atrapar el error, guardar el archivo pendiente en algún lado, reintentar más tarde sin perder la cuenta y sin reintentar para siempre | El dato espera en una **cola**; reintentos con espera creciente; lo que falla de verdad va a una carpeta de errores |
| El mismo archivo llega **dos veces**. | Detectar repetidos antes de insertar | NiFi no lo evita (entrega *al menos una vez*): lo resuelve el destino, con clave primaria + `INSERT_IGNORE` |

**Apache NiFi** es una plataforma cuyo único trabajo es **mover datos entre sistemas**: sacarlos de un lado, enrutarlos, transformarlos un poco y entregarlos en otro. El flujo no se escribe en código: se **dibuja** en un canvas web, con cajas y flechas. NiFi corre como un servicio permanente y el flujo trabaja todo el tiempo, no cuando alguien lo ejecuta.

## 2. El modelo mental, antes de tocar nada

Seis palabras. Si se entienden estas, el resto del lab es configurar.

- **FlowFile.** Lo que viaja por NiFi. Tiene dos partes, como una carta en un sobre: el **contenido** (los bytes: aquí, el CSV completo de una hora) y los **atributos** (etiquetas `clave = valor` pegadas en el sobre: `filename`, `absolute.path`, `file.size`, `uuid`…). Los procesadores pueden decidir mirando solo las etiquetas, sin abrir el sobre.
- **Procesador.** Una caja que hace **una sola cosa**: listar una carpeta, leer un archivo, insertar en una base, escribir en Redis. Recibe FlowFiles y entrega FlowFiles.
- **Relationship (relación).** Cada salida posible de un procesador: `success`, `failure`, `retry`, `not.found`… Cada una se **conecta** a otro procesador o se **termina** (*terminate*: el FlowFile se descarta ahí). Si una queda suelta, el procesador no arranca.
- **Connection y su cola.** La flecha entre dos procesadores. **Adentro tiene una cola**: los FlowFiles que la caja de abajo todavía no toma esperan ahí, en disco.
- **Process Group.** Una carpeta del canvas para ordenar: el lab entero vive en un grupo llamado `Lab 10`.
- **Controller service.** Configuración **compartida** que usan varios procesadores: cómo leer un CSV (`CSVReader`), cómo conectarse a Postgres (`DBCPConnectionPool`). Se configura una vez y se **habilita**.

El flujo del lab, con cada término señalado:

```text
                       ┌── connection (con su cola) ──┐
                       │                              ▼
 [ListFile] ─success─▶ [FetchFile] ─success─▶ [PutDatabaseRecord] ─failure, retry─▶ [PutFile]
  procesador     ▲         │                      │  usa: CSVReader +                /data/errores
                 │         │                      │       DBCPConnectionPool  ◀── controller services
       relationship        │                   success → terminate
                           │
                           └─success─▶ [QueryRecord] ─estado─▶ [PutRedisHashRecord]
                                           │  usa: CSVReader + JsonRecordSetWriter     usa: JsonTreeReader +
                                           │                                                RedisConnectionPoolService
                                           └─alertas─▶ [LogAttribute]
 todo esto dentro del Process Group «Lab 10» · lo que viaja por cada flecha: FlowFiles
```

**Por debajo, tres repositorios en disco.** El *FlowFile repository* guarda qué FlowFiles existen, en qué cola está cada uno y sus atributos. El *Content repository* guarda los bytes del contenido, una sola vez: entre cajas viaja solo una referencia, así que mover un FlowFile de 424 KB es barato. Si un procesador cambia el contenido, se escribe una versión nueva y la vieja se conserva un tiempo (*copy-on-write*). El *Provenance repository* guarda la historia de cada FlowFile: quién lo creó, por dónde pasó, cuándo salió. Por estar en disco, si NiFi se reinicia con tres FlowFiles en una cola, siguen ahí al volver.

## 3. El canvas, pieza por pieza

Lo que van a ver en NiFi 2 (la interfaz cambió bastante respecto de NiFi 1: si buscan ayuda en internet, fíjense en la versión).

- **La barra de componentes**, arriba a la izquierda: íconos que se **arrastran** al canvas. El primero es *Processor*; también están *Process Group*, *Funnel* y otros que no usamos.
- **Agregar un procesador:** arrastren el ícono de *Processor* al canvas y suelten. Se abre un diálogo con un buscador, *Filter types*: escriban parte del nombre (`ListFile`), elijan el tipo y hagan clic en *Add*.
- **Configurar:** doble clic sobre la caja, o clic derecho → *Configure*. El diálogo tiene pestañas:
  - *Settings*: el nombre de la caja y ajustes generales.
  - *Scheduling*: cada cuánto corre (*Run Schedule*).
  - *Properties*: lo que hace la caja. Las propiedades obligatorias que faltan aparecen marcadas. El **+** de arriba a la derecha (*Add Property*) agrega una propiedad nueva, que usamos en `QueryRecord`.
  - *Relationships*: la lista *Automatically Terminate/Retry Relationships*, con dos casillas por relación: **terminate** y **retry**.
- **Conectar:** al pasar el mouse por el centro de una caja aparece una flecha. Arrástrenla hasta la otra caja y elijan qué relaciones van por esa connection (pueden ser varias).
- **Iniciar y detener:** clic derecho → *Start* / *Stop*. En un espacio vacío del canvas, el mismo menú inicia o detiene todo el grupo.
- **Los *controller services*:** clic derecho en un espacio vacío del canvas (dentro del grupo) → *Controller Services*. Ahí se crean (**+**), se configuran (engranaje) y se habilitan (rayo, *Enable*) o deshabilitan (*Disable*). Un servicio habilitado no se puede editar: para cambiarlo, detengan los procesadores que lo usan y deshabilítenlo.
- **El triángulo amarillo:** el procesador está mal configurado y no puede arrancar. Pasen el mouse por encima: dice qué falta (una propiedad, una relación sin resolver, un servicio deshabilitado).
- **El cuadrito rojo (*bulletin*):** en la esquina de un procesador que corre, avisa que algo falló. Pasen el mouse: muestra el error. En la diap. 12 lo van a ver en `PutDatabaseRecord`.
- **Las colas:** sobre cada connection, cuántos FlowFiles hay y cuánto pesan. Clic derecho en la connection:
  - *List Queue*: la lista de FlowFiles que esperan. El menú de cada uno tiene *View details* (sus atributos, en *Attribute Values*), *View content* (el contenido), *Download content* y *Provenance*.
  - *Empty Queue*: descarta todo lo que hay en la cola. No se recupera.
  - *Configure*: el *Back Pressure Object Threshold* y el *Size Threshold* (sección 6).
- **View State:** clic derecho en `ListFile` → *View State*. Muestra lo que el procesador recuerda (la fecha del último archivo listado). *Clear state* lo borra y `ListFile` vuelve a listar todo.
- **Data Provenance:** clic derecho en un procesador → *View Data Provenance*. Una tabla de eventos, uno por cada cosa que le pasó a cada FlowFile. En el lab aparecen `CREATE` (`ListFile` lo creó), `FETCH` (`FetchFile` cargó el contenido), `CLONE` (se copió para la segunda rama), `ROUTE` (`QueryRecord` lo mandó por una relación), `SEND` (salió hacia Postgres o Redis) y `DROP` (terminó su recorrido). Desde el menú de una fila: *View Details* (atributos y contenido de ese momento) y *Show Lineage* (el dibujo de su historia). El botón *Replay* vuelve a mandar ese FlowFile desde ese punto.

## 4. Los procesadores del lab, uno por uno

### `ListFile` — avisa que llegó un archivo

Mira una carpeta y, por cada archivo nuevo, emite un FlowFile **sin contenido**, solo con atributos (`filename`, `absolute.path`, `file.size`…).

| Propiedad | Valor | Por qué |
|---|---|---|
| Input Directory | `/data/entrada` | la carpeta, vista desde **adentro** del contenedor (`./entrada` afuera) |
| File Filter | `eventos_.*\.csv` | una expresión regular: solo los archivos del lab |
| *Run Schedule* (Scheduling) | `5 sec` | por defecto mira cada **1 min**; para el lab es demasiado lento |

Relación: `success`. **Cómo recuerda:** con *Listing Strategy* = `timestamps` (por defecto) guarda en su *state* la fecha de modificación más reciente que ya listó. Un archivo con fecha más nueva es «nuevo». Por eso `cp` de un archivo ya listado lo hace aparecer otra vez: `cp` le pone la fecha de ahora. Y por eso no importa si copian el archivo antes de iniciar `ListFile`: al arrancar, lo ve igual.

### `FetchFile` — trae el contenido

Toma el FlowFile vacío de `ListFile` y le carga el contenido del archivo.

| Propiedad | Valor | Por qué |
|---|---|---|
| File to Fetch | `${absolute.path}/${filename}` (por defecto) | arma la ruta con los atributos que dejó `ListFile`: Expression Language (sección 8) |
| Completion Strategy | `None` (por defecto) | qué hacer con el archivo original después: `None`, `Move File` o `Delete File`. Lo dejamos donde está |

Relaciones: `success`, `not.found`, `permission.denied`, `failure`. En el lab las tres últimas se terminan: si algo falla, el archivo sigue en `entrada/` y no se pierde nada.

**¿Por qué dos cajas y no una?** Existe `GetFile`, que lista y lee en una sola caja, pero por defecto **borra el archivo** de la carpeta al leerlo (*Keep Source File* = `false`). Separados, `ListFile` decide **qué** hay que leer y `FetchFile` solo **lee**. En un clúster, un nodo lista y varios leen en paralelo. Y la carpeta queda intacta.

### `PutDatabaseRecord` — inserta las filas en Postgres

Lee el contenido como registros (con un *Reader*) y los inserta en una tabla.

| Propiedad | Valor | Por qué |
|---|---|---|
| Record Reader | `CSVReader` | cómo leer el contenido (sección 5) |
| Database Type | `PostgreSQL` | para que escriba el SQL en el dialecto de Postgres |
| Statement Type | `INSERT_IGNORE` | `INSERT … ON CONFLICT (estacion_id, ts) DO NOTHING`: si la clave ya está, la fila se salta |
| Database Connection Pooling Service | `DBCPConnectionPool` | la conexión compartida |
| Table Name | `eventos` | la tabla destino; NiFi lee sus columnas y las calza por nombre con los campos del CSV |

Relaciones: `success`, `failure` y `retry`. `retry` es para lo que podría funcionar más tarde; `failure`, para lo que no. En el lab, con Postgres caído el procesador manda el FlowFile por **`failure`** (el bulletin dice *Routing to failure*). Por eso la casilla **retry** se marca en las dos: así el FlowFile no se va a `errores/` mientras quede algún intento.

**Los reintentos** (*Relationships*, con la casilla **retry** marcada):

| Ajuste | Valor | Qué hace |
|---|---|---|
| Number of Retry Attempts | `10` | cuántas veces lo intenta antes de mandarlo por la relación de verdad |
| Retry Back Off Policy | `Penalize` | el FlowFile que falló vuelve a su cola de entrada **penalizado**: espera antes del próximo intento, y la espera crece. La otra opción, `Yield`, detiene el procesador entero hasta terminar los reintentos |
| Retry Maximum Back Off Period | `30 sec` | la espera nunca pasa de 30 s |

Si una relación tiene marcadas **retry** y **terminate**, primero se reintenta y recién al agotar los intentos se termina. En el lab, `failure` y `retry` no se terminan: van a `PutFile`. Agotados los 10 intentos (unos 5 minutos), el FlowFile termina en `errores/`. Nada se descarta en silencio.

### `PutFile` — la cola de descarte

Escribe el contenido del FlowFile como archivo en una carpeta.

| Propiedad | Valor | Por qué |
|---|---|---|
| Directory | `/data/errores` | `./errores` afuera: lo que no se pudo cargar queda ahí, con su nombre original |
| Conflict Resolution Strategy | `replace` | si ya hay un archivo con ese nombre, lo reemplaza (por defecto `fail`) |

Relaciones: `success` y `failure`, las dos terminadas. Si un archivo llega aquí, se arregla la causa y se vuelve a copiar a `entrada/`.

### `QueryRecord` — SQL sobre el FlowFile

Corre consultas SQL sobre los registros del FlowFile. **Cada propiedad nueva que le agregan es una consulta y, a la vez, una relación de salida** con ese nombre.

| Propiedad | Valor | Por qué |
|---|---|---|
| Record Reader | `CSVReader` | el contenido llega como CSV |
| Record Writer | `JsonRecordSetWriter` | el resultado sale como JSON, que es lo que lee la rama de Redis |
| `estado` (nueva) | `SELECT 'sensor:' \|\| estacion_id AS clave, estacion_id, tipo_sensor, valor, ts FROM FLOWFILE` | agrega a cada fila el nombre del hash de Redis |
| `alertas` (nueva, si terminan antes) | `SELECT * FROM FLOWFILE WHERE tipo_sensor = 'calidad_aire' AND valor > 70` | solo las lecturas altas de aire |

Relaciones: `original` (el FlowFile tal como entró), `failure` y una por cada propiedad nueva. `original` y `failure` se terminan. El FlowFile que sale por una consulta lleva el atributo `record.count`: cuántas filas devolvió. Para `alertas` con el archivo de las 09:00, **570**.

### `PutRedisHashRecord` — un `HSET` por fila

Por cada registro escribe un hash en Redis: la clave sale de un campo y los campos del hash, del registro.

| Propiedad | Valor | Por qué |
|---|---|---|
| Record Reader | `JsonTreeReader` | el contenido llega como JSON desde `QueryRecord` |
| Redis Connection Pool | `RedisConnectionPoolService` | la conexión compartida |
| Hash Value Record Path | `/clave` | de qué campo sale el nombre del hash: `sensor:CC-004` (RecordPath, sección 8) |
| Data Record Path | `/` (por defecto) | qué parte del registro va como campos del hash: todo |

Relaciones: `success` y `failure`, terminadas. Como `/` es el registro entero, el campo `clave` **también** queda dentro del hash. Las filas van en orden y cada `HSET` pisa al anterior, así que la última fila de cada sensor queda como su estado actual.

### Los que se usan de paso

- `GenerateFlowFile` (diap. 7): fabrica FlowFiles con el texto de *Custom Text*. Sirve para probar.
- `LogAttribute`: escribe los atributos del FlowFile en el log de NiFi (`docker compose logs nifi`). Con *Log Payload* = `true`, también el contenido. Su única relación, `success`, se termina.
- `ReplaceText` e `InvokeHTTP` (bonus): el primero envuelve el texto del FlowFile con *Text to Prepend* y *Text to Append* (*Replacement Strategy* = `Surround`, *Evaluation Mode* = `Entire text`). El segundo lo manda por HTTP. `InvokeHTTP` tiene cinco relaciones: `Response` (la respuesta del servidor), `Original` (lo que se mandó), `Failure`, `No Retry` y `Retry`.

## 5. Registros: un FlowFile, miles de filas

El archivo de las 08:00 tiene 7.200 filas y entra como **un** FlowFile de ~424 KB, no como 7.200. Los procesadores *Record* (`PutDatabaseRecord`, `QueryRecord`, `PutRedisHashRecord`) leen ese contenido como una secuencia de **registros con esquema**, sin partirlo. Es mucho más barato: una cola con 1 objeto en vez de 7.200, y un solo evento de procedencia por archivo.

- Un ***Reader*** dice cómo leer (CSV, JSON…) y un ***Writer***, cómo escribir. Son *controller services*: los configuran una vez y los usan varios procesadores. En el lab el mismo `CSVReader` lo usan `PutDatabaseRecord` y `QueryRecord`.
- **El esquema** (qué campos y de qué tipo) se puede **inferir** mirando los datos (*Schema Access Strategy* = `Infer Schema`, lo que hicimos) o **declarar** (por ejemplo, un esquema Avro en *Schema Text*). Inferir es cómodo; declarar evita sorpresas.

**Lo que infirió el `CSVReader` en el lab:** `estacion_id` y `tipo_sensor` como texto, `valor` como `float` y **`ts` como texto**, aunque parezca una fecha. Probamos con *Timestamp Format* = `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` y con otras variantes del formato: igual infiere texto. Por eso `PutDatabaseRecord` mandaba `ts` como `character varying` y Postgres lo rechazaba, porque la columna es `timestamptz`. La solución del lab está en la URL de conexión: `?stringtype=unspecified` le dice al driver JDBC que mande los textos «sin tipo» y deje que Postgres los convierta a lo que pide la columna. Postgres sí entiende `2026-11-13T08:00:01.000-03:00`. La otra salida habría sido declarar el esquema, con `ts` como `timestamp-millis`.

Y el `80` sin decimal: el generador escribe `80.0`, no `80`, porque al inferir, un `80` suelto podría tomarse como entero, y un archivo podría quedar con `valor` entero y el siguiente con decimal. Con un decimal siempre, el tipo es el mismo en todas las filas y en todos los archivos.

En Redis, como `ts` viajó como texto, queda escrito tal cual venía en el CSV: `2026-11-13T09:59:53.500-03:00`.

**`QueryRecord` y `FLOWFILE`.** Dentro de `QueryRecord`, `FLOWFILE` es el nombre de la tabla: los registros del FlowFile que está procesando. El SQL es estándar (lo ejecuta Apache Calcite). Por eso la columna se llama `ts` y no `timestamp`: `timestamp` es palabra reservada.

## 6. Cuando algo falla

**Colas y umbrales.** Cada connection tiene dos umbrales: *Back Pressure Object Threshold* (por defecto **10.000** FlowFiles) y *Size Threshold* (por defecto **1 GB**). Si la cola llega a cualquiera de los dos, se dice que está llena.

**Back-pressure.** Cuando una cola está llena, NiFi **deja de programar** al procesador que la alimenta: la caja de arriba se frena hasta que haya espacio. Como esa caja ya no consume, su propia cola de entrada empieza a crecer, y si se llena frena a la de más arriba. El freno se **propaga hacia atrás**, cola por cola, hasta la fuente.

**Lo que pasó en la diap. 12, con el umbral en 1:**

1. Postgres se cae. El archivo de las 10:00 llega a `PutDatabaseRecord`, falla, y por la casilla **retry** vuelve a su cola de entrada, penalizado. La cola `FetchFile → PutDatabaseRecord` queda en **1/1**: llena.
2. `FetchFile` tiene **dos** salidas por `success` (Postgres y Redis). Basta con que una esté llena para que NiFi no lo programe: se frena entero. El archivo de las 10:00 ya había salido también hacia `QueryRecord`, así que Redis lo recibió (77.3), pero los de 11:00 y 12:00 se quedan esperando en la cola `ListFile → FetchFile` (**2**).
3. Postgres vuelve. El siguiente reintento (a lo más 30 s después) funciona, la cola de adelante se vacía primero, `FetchFile` vuelve a correr y los otros dos archivos pasan, en orden, por las dos ramas. En el ensayo, todo quedó en cero unos 30 s después del `docker start`.

Por eso **una base caída frena también a Redis**: las dos ramas salen del mismo procesador. Es una decisión de diseño, no un error. Si no se quiere ese acoplamiento, se sube el umbral de esa cola (que aguante más espera) o se separan las ramas.

**Reintentos sin lazo.** También se podría conectar `retry` de vuelta al mismo `PutDatabaseRecord`. Pero así el FlowFile **sale** de la cola de entrada y vuelve por otra connection: la cola `FetchFile → PutDatabaseRecord` no se llena, `FetchFile` sigue trabajando y Redis no se frena. Con la casilla **retry**, el FlowFile espera en su lugar.

**La cola de descarte.** Lo que no se pudo cargar después de todos los intentos va a `PutFile` → `errores/`. **Nada se descarta en silencio**: o llegó, o está en una cola, o está en `errores/`, y en los tres casos queda en la procedencia.

## 7. Garantías e idempotencia

**Al menos una vez.** NiFi garantiza que un dato llega **al menos una vez**: si hay duda (un timeout, un reinicio a mitad de camino), reenvía. Por lo tanto, un dato **puede llegar dos veces**. Además, el mundo reenvía solo: el generador repite el 2 % de los eventos y alguien copia de nuevo el archivo de las 08:00 (diap. 13).

**Idempotencia en el destino.** Una operación es *idempotente* si hacerla dos veces deja lo mismo que hacerla una. Como NiFi puede entregar dos veces, el que tiene que ser idempotente es el destino:

| Destino | Cómo | Resultado en el lab |
|---|---|---|
| Postgres | clave primaria `(estacion_id, ts)` + `INSERT_IGNORE` | 7.200 filas → 7.063; reenviar 0800 deja 35.310 |
| Neo4j (C12 y bonus) | `MERGE` en vez de `CREATE` | el mismo sensor no se crea dos veces |
| Redis | `HSET` | un repetido deja el mismo estado, pero un dato **viejo** lo hace retroceder |

**Por qué Redis retrocede.** `HSET` escribe lo último que llega, sin mirar el tiempo. Al reenviar el archivo de las 08:00, la última fila de `CC-004` en ese archivo es la de las 08:59:47, y queda como «estado actual» aunque Redis ya tenía la de las 12:59:55. Postgres no sufre esto porque guarda todas las filas y la clave descarta las repetidas. Para arreglarlo, habría que escribir solo si el `ts` que llega es más nuevo que el guardado: leer antes y comparar, o un script Lua en Redis que lo haga en una sola operación. Queda como pregunta para pensar.

Lo mismo pasa dentro de un mismo archivo. En el de las 13:00, la última fila de `PEN-001` es un evento **tardío** (`13:58:16.938`) aunque hay filas posteriores: Redis queda con ese, porque fue el último en llegar.

## 8. Los tres minilenguajes

NiFi tiene tres lenguajes chicos, y en el lab se usan los tres.

**Expression Language (EL)** — se escribe `${…}` y trabaja con **atributos**.

```text
${absolute.path}/${filename}     → /data/entrada/eventos_0800.csv      (File to Fetch de FetchFile)
${filename:substringBefore('.')} → eventos_0800
${file.size:gt(400000)}          → true
```

Solo lo que va entre `${` y `}` es EL. Por eso, en la plantilla del bonus, `$filas` (sin llaves) pasa tal cual hasta Neo4j.

**RecordPath** — se escribe como una ruta `/campo` y trabaja **dentro de un registro**.

```text
/clave           → sensor:CC-004   (Hash Value Record Path de PutRedisHashRecord)
/                → el registro completo (Data Record Path)
/valor           → 69.8
```

**SQL de `QueryRecord`** — consultas sobre la tabla `FLOWFILE`, que son los registros del FlowFile.

```sql
SELECT 'sensor:' || estacion_id AS clave, estacion_id, tipo_sensor, valor, ts FROM FLOWFILE
SELECT * FROM FLOWFILE WHERE tipo_sensor = 'calidad_aire' AND valor > 70
SELECT estacion_id, tipo_sensor, COUNT(*) AS n, AVG(valor) AS promedio, MAX(ts) AS ultimo_ts
FROM FLOWFILE GROUP BY estacion_id, tipo_sensor
```

Para no confundirlos: **EL** mira las etiquetas del sobre; **RecordPath**, un campo de una fila; **SQL**, todas las filas a la vez.

## 9. Errores frecuentes

| Lo que se ve | La causa |
|---|---|
| Triángulo amarillo: *'Relationship X' is invalid because Relationship 'X' is not connected to any component and is not auto-terminated* | una relación sin resolver: conéctenla o márquenla **terminate** en *Relationships* |
| Triángulo amarillo que menciona un *Controller Service* deshabilitado | falta habilitar el servicio (rayo, *Enable*) |
| `DBCPConnectionPool` no habilita | la ruta del JAR en *Database Driver Locations*: tiene que ser `/opt/nifi/drivers/` + el nombre exacto |
| Bulletin de `PutDatabaseRecord`: *column "ts" is of type timestamp with time zone but expression is of type character varying* | el lector infirió `ts` como texto: falta `?stringtype=unspecified` en la URL de conexión (sección 5) |
| Bulletin de `PutDatabaseRecord`: *Failed to put Records to database … Routing to failure* | Postgres no responde (en la diap. 12, a propósito). Con la casilla **retry**, el FlowFile espera y reintenta |
| Postgres con 7.200 filas después del primer archivo | el *Statement Type* no es `INSERT_IGNORE`, o la tabla no tiene la clave primaria (`\d eventos`) |
| `ListFile` corre y no aparece nada | el *Input Directory* es la ruta de afuera (`./entrada`) en vez de la de adentro (`/data/entrada`), o el *File Filter* no calza; o el archivo ya se listó (`cp` de nuevo, o *View State → Clear state*) |
| *connection refused* en el navegador | NiFi todavía está arrancando |
| El bonus no escribe en Neo4j y no hay ningún error rojo | Neo4j respondió 200 con el error dentro de `errors`: mírenlo en el `LogAttribute` con *Log Payload* = `true` |

## 10. Puente a la C15

NiFi reacciona al **dato**: apenas aparece un archivo en `entrada/`, lo mueve. Es lo correcto para un flujo continuo entre sistemas. Pero hay trabajos de otra forma:

> ¿Y si el proceso tiene que correr **a las 03:00 cada noche**, **solo si terminó otro antes**, y **avisar por correo si falla**?

Eso ya no es «mover cada dato cuando llega», sino **orquestar tareas en el tiempo**, con dependencias entre ellas. En la próxima clase lo resolvemos con Airflow y n8n, sobre los mismos seis archivos de hoy y la misma tabla `eventos`.
