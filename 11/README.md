# Laboratorio 11 — Clase 15 (Vie 20-nov): Airflow y n8n, orquestar los CSV de la C14

> Segunda clase del bloque ETL. Usamos **los mismos seis CSV** de la C14 y la misma tabla `eventos` de Postgres, pero ahora no los mueve NiFi: los carga un DAG de Airflow, hora por hora, y n8n recibe el aviso. La teoría va primero en el deck; este README es la receta de la práctica, diapositiva por diapositiva (9 a 18). **No hay notebook:** después de cada paso, `python3 checkpoint.py` les dice si las tablas quedaron como deben. Material de estudio: [`CONTENTS.md`](CONTENTS.md) (léanlo si nunca han usado Airflow ni n8n: explica cada pieza, cada menú y cada línea de los DAGs).

*Libreto: `Clases/Clase 15 (2011)/Clase 15 (2011) — Libreto.md` · guía docente: `Clases/Clase 15 (2011)/Clase 15 (2011) — Laboratorio 11.md` (en la carpeta del curso, fuera de este repositorio).*

En la C14 NiFi reaccionaba al **archivo**: si aparecía, lo movía. Hoy Airflow se pregunta por cada **hora**: ¿ya se procesó la de las 11:00? ¿Falló? ¿Hay que repetirla? Y la deuda de la C14: «¿y si tiene que correr a las 03:00, solo si terminó otro antes, y avisar si falla?».

## Qué se necesita

- **Docker** con `docker compose` y ~3 GB de RAM libre (el stack usa ~2,5 GB: Airflow ~2 GB, n8n ~0,5 GB, Postgres ~40 MB).
- Las imágenes, descargadas **antes** de clase (el viernes no se descarga nada):

  ```bash
  docker compose pull      # Airflow ~660 MB y n8n ~380 MB de descarga (~5,5 GB en disco); Postgres ya está de los labs anteriores
  ```

- Los datos, una vez:

  ```bash
  python3 preparar_datos.py
  ```

  Tiene que terminar con `Verificación OK: 6 archivos · 43.200 filas · 42.368 claves únicas → data/`. Copia los seis CSV de `../10/pendientes/` a `data/` y los compara byte a byte. Si no están, los genera primero con `../10/preparar_datos.py` (el mismo generador del Lab 06).

No hace falta ningún paquete de Python: `preparar_datos.py` y `checkpoint.py` usan solo la biblioteca estándar.

> ⚠️ **Nada del Lab 10 corriendo.** Este lab usa el mismo nombre `pmd-postgis`, y NiFi ocupa memoria que Airflow necesita:
>
> ```bash
> docker compose -f ../10/docker-compose.yml --profile bonus down -v
> docker rm -f pmd-postgis pmd-airflow pmd-n8n     # si docker compose up dice «container name … already in use»
> ```

## El stack

```bash
docker compose up -d --wait            # levantar y esperar a que los tres respondan (entre 15 s y 2 min)
open http://localhost:8080             # Airflow (Windows/Linux: ábranlo en el navegador)
open http://localhost:5678             # n8n
docker compose down -v                 # al terminar: apagar todo y borrar los volúmenes
```

| Servicio | Contenedor | Puerto en su máquina | Para qué | Cómo lo nombran los otros |
|---|---|---|---|---|
| Airflow 3.4.0 | `pmd-airflow` | `8080` | los DAGs: <http://localhost:8080> | — |
| Postgres 16 | `pmd-postgis` | `5433` | las cuatro tablas | `postgres:5432` |
| n8n 2.48.6 | `pmd-n8n` | `5678` | el workflow que recibe el aviso: <http://localhost:5678> | `n8n:5678` |

Los tres están en la misma red de Docker y se hablan **por el nombre del servicio**. Dentro del contenedor de Airflow, `localhost` es el propio Airflow, no su máquina: por eso el DAG llama a `http://n8n:5678/…` y la conexión a Postgres usa `postgres:5432`.

Airflow ve dos carpetas de su máquina, montadas adentro:

| Afuera (su máquina) | Adentro (Airflow) | Qué hay |
|---|---|---|
| `./dags/` | `/opt/airflow/dags` | los dos DAGs: Airflow lee esta carpeta y los muestra en la interfaz |
| `./data/` | `/opt/airflow/data` | los seis CSV: el DAG los busca aquí, por la ruta de adentro |

**Airflow no pide clave** (solo para el lab: `SIMPLE_AUTH_MANAGER_ALL_ADMINS`). **n8n ya trae la cuenta del curso:** correo `pmd@usm.cl`, clave `Pmd2026pmd2026`. La crea el compose; no hay formulario de dueño.

**Idioma y hora.** La interfaz de Airflow sale en el idioma del navegador (en español, *Clear* es «Limpiar») y muestra las horas en la zona del navegador. Si ven las ejecuciones como 12:00 … 17:00 en vez de 09:00 … 14:00, están en UTC: hagan clic en el **reloj** de la barra izquierda (abajo, dice `-03:00` o `UTC`) → *Select Timezone* («Seleccionar Zona Horaria») → `America/Santiago`. n8n está en inglés.

## Los datos

Los seis archivos de la C14, sin cambios: seis horas de los 16 sensores del 13-nov (08:00 a 13:59), en el orden en que llegaron. Cabecera `estacion_id,tipo_sensor,valor,ts`.

| Archivo | Filas | Únicas `(estacion_id, ts)` |
|---|---|---|
| `eventos_0800.csv` | 7.200 | 7.063 |
| `eventos_0900.csv` | 7.200 | 7.037 |
| `eventos_1000.csv` | 7.200 | 7.062 |
| `eventos_1100.csv` | 7.200 | 7.074 |
| `eventos_1200.csv` | 7.200 | 7.074 |
| `eventos_1300.csv` | 7.200 | 7.058 |

**La columna `ts` es la que manda, no el nombre del archivo.** `eventos_0900.csv` trae algunos eventos con `ts` de las 08:59 que llegaron tarde (los tardíos del Lab 06). Eso va a importar en la diapositiva 13.

## La receta

Dos reglas para todos los pasos:

- **Los comandos de terminal se escriben en `Laboratorios/11/`**, en su máquina (no dentro de un contenedor).
- **En Airflow, *Clear* se hace desde el cuadrito de la tarea** en la vista *Grid*: clic en el cuadrito → botón ↻ arriba a la derecha (*Clear Task Instance*, «Limpiar Instancia de Tarea») → elegir las opciones → *Confirm*. Antes de confirmar, el diálogo dice cuántas tareas va a limpiar (*Affected Tasks*, «Tareas Afectadas»): úsenlo para revisar.

### Diapositiva 9 — Levantar el stack

```bash
docker compose up -d --wait
docker compose ps
python3 checkpoint.py
```

Abran <http://localhost:8080> (entra directo, sin login) y <http://localhost:5678> (*Sign in* con `pmd@usm.cl` / `Pmd2026pmd2026`). Si n8n abre su asistente (*n8n Assistant*), elijan *Set up later in Settings*.

**Resultado esperado:** `docker compose ps` con los tres servicios `healthy`; en Airflow, la lista de DAGs con `eventos_por_hora` y `resumen_diario`, los dos **apagados**; n8n sin workflows; `✓ Calza con: el inicio`.

### Diapositiva 10 — Leer el DAG

Abran `dags/eventos_por_hora.py` en su editor (o, en Airflow, el DAG → pestaña *Code*). Son cuatro tareas en cadena: `buscar_archivo → cargar → resumir → avisar`. En Airflow, el DAG → vista *Graph* muestra la misma cadena.

> 🤔 **Antes de ejecutar:** el DAG empieza el 13-nov y hoy es 20-nov. Al encenderlo, ¿cuántas ejecuciones va a crear Airflow?

**Resultado esperado:** la vista *Graph* con las cuatro cajas en fila, sin ejecuciones todavía.

### Diapositiva 11 — Encenderlo, con un archivo perdido

Antes de encender, alguien «pierde» el archivo de las 11:00:

```bash
mkdir -p escondido && mv data/eventos_1100.csv escondido/
```

Enciendan `eventos_por_hora` con su interruptor (en la lista de DAGs, o arriba a la derecha en la página del DAG) y miren la vista *Grid*: columnas = ejecuciones, filas = tareas. En un minuto aparecen las seis. Hagan clic en el cuadrito rojo y miren su log: arriba, *Task Tries* («Intentos de Tarea») muestra los tres intentos (1 + 2 reintentos, con 15 s entre ellos) y el `FileNotFoundError`.

```bash
docker exec pmd-postgis psql -U postgres -c "SELECT count(*) FROM eventos;"
python3 checkpoint.py
```

> 🤔 **Antes de ejecutar:** ¿qué habría pasado en NiFi con el archivo perdido?

**Resultado esperado:** 6 columnas (09:00 … 14:00): 5 verdes y la de las **12:00** con `buscar_archivo` en rojo y las otras tres tareas en naranjo (*upstream_failed*). `count` = **35.294** · `✓ Calza con: después de la diapositiva 11`.

### Diapositiva 12 — Reparar: devolver el archivo y *Clear*

```bash
mv escondido/eventos_1100.csv data/
```

En el *Grid*: clic en el cuadrito rojo (`buscar_archivo` de las 12:00) → ↻ → *Downstream* (ya viene marcado) → *Affected Tasks: 4* → *Confirm*.

```bash
docker exec pmd-postgis psql -U postgres -c \
  "SELECT count(*) FROM eventos; SELECT count(*) FROM resumen_horario;"
python3 checkpoint.py
```

**Resultado esperado:** el *Grid* entero en verde. `eventos` = **42.368** (el mismo número del final de la C14) · `resumen_horario` = **96** filas (16 sensores × 6 horas) · `✓ Calza con: después de la diapositiva 12`.

### Diapositiva 13 — Los datos tardíos

```sql
SELECT (SELECT count(*) FROM eventos) AS eventos,
       (SELECT sum(n) FROM resumen_horario) AS en_resumenes;
```

(En la terminal: `docker exec -it pmd-postgis psql -U postgres` y peguen la consulta; `\q` para salir.)

> 🤔 **Antes de ejecutar:** ¿por qué no calzan los dos números? Pista: los tardíos del Lab 06.

Ahora reprocesen **todo**: clic en el cuadrito de `buscar_archivo` de la ejecución de las **09:00** → ↻ → marquen *Future* («Futuro») además de *Downstream* → *Affected Tasks: 24* → *Confirm*. Las seis vuelven a correr, de a una.

```bash
python3 checkpoint.py
docker exec pmd-postgis psql -U postgres -c \
  "SELECT hora, n, round(promedio::numeric, 2) FROM resumen_horario WHERE estacion_id = 'CC-004' ORDER BY hora;"
```

**Resultado esperado:** antes del *Clear*, `eventos` = 42.368 y `en_resumenes` = **42.344**. Después: `en_resumenes` = **42.363** · `✓ Calza con: después de la diapositiva 13`. CC-004: 73.04 · 73.88 · 74.19 · 74.62 · 74.54 · **73.85** (08:00 → 13:00).

### Diapositiva 14 — n8n: un workflow que recibe un aviso

En n8n: *Create workflow* (o el **+** de la barra izquierda). Cada nodo se agrega con el **+** y se busca por su nombre.

| Nodo | Opción | Valor |
|---|---|---|
| **Webhook** | HTTP Method | `POST` |
| | Path | `alerta-aire` |
| | Respond | `Using 'Respond to Webhook' Node` |
| **If** | Conditions | valor `{{ $json.body.estaciones.length }}` · operador *Number → is greater than* · `0` |
| **Respond to Webhook** (salida `true`) | Respond With | `JSON` |
| | Response Body | `{"alerta": true}` |
| **Respond to Webhook** (salida `false`) | Respond With | `JSON` |
| | Response Body | `{"alerta": false}` |

Para probar: botón **Execute** (abajo, al centro del lienzo). n8n se queda escuchando la URL de **prueba**; desde la terminal:

```bash
curl -X POST http://localhost:5678/webhook-test/alerta-aire \
  -H "Content-Type: application/json" \
  -d '{"hora": "2026-11-13T13:00:00-03:00", "estaciones": [["CC-004", 73.85]]}'
```

Vuelvan a apretar **Execute** y repitan con `"estaciones": []`. La URL de prueba sirve para **una** llamada por cada *Execute*.

Ojo: el botón *Listen for test event* que aparece dentro del nodo Webhook prueba **solo ese nodo**: `curl` recibe un 200 vacío. Para probar el flujo completo, **Execute** del lienzo.

**Resultado esperado:** `{"alerta":true}` con CC-004 y `{"alerta":false}` con la lista vacía; en el lienzo, el camino recorrido en verde.

### Diapositiva 15 — Publicar y conectar: Airflow avisa a n8n

En n8n: **Publish** (arriba a la derecha). El botón pasa a decir *Published* y desde ahí existe la URL de **producción**, `/webhook/alerta-aire`. Si cambian algo después, quedará en borrador hasta volver a publicar.

En Airflow: clic en el cuadrito de `avisar` de la ejecución de las **14:00** → ↻ → *Confirm* (*Affected Tasks: 1*). Abran su log.

```bash
curl -X POST http://localhost:5678/webhook/alerta-aire \
  -H "Content-Type: application/json" -d '{"estaciones": []}'
```

**Resultado esperado:** el log de `avisar` dice `n8n respondió: 200 {"alerta":true}`. En n8n, pestaña **Executions** (arriba, al centro): la llamada que llegó desde Airflow, con `estaciones = [["CC-004", 73.85]]`. Antes de publicar, ese mismo log decía `n8n respondió: 404 … not registered`.

### Diapositiva 16 — El DAG de las 03:00

Abran `dags/resumen_diario.py`: dos tareas, `verificar_horas → resumir_dia`, a las 03:00. `verificar_horas` revisa que estén las 96 filas horarias del día anterior; si faltan, **falla** y `resumir_dia` no corre. Es el «solo si terminó lo anterior» de la deuda de la C14.

Enciendan `resumen_diario` con su interruptor.

```bash
python3 checkpoint.py
docker exec pmd-postgis psql -U postgres -c \
  "SELECT estacion_id, n, round(promedio::numeric, 2) FROM resumen_diario ORDER BY estacion_id;"
```

> 🤔 **Antes de ejecutar:** ¿por qué el promedio del día no es el promedio de los seis promedios horarios? Compárenlo para CHI-001.

**Resultado esperado:** **una** ejecución (14-11 03:00), en verde. `resumen_diario` = 16 filas con `sum(n)` = 42.363 · CC-004 con `n` = 2.752 y 74.02 · CHI-001 65.73 · TAL-003 62.67 · COR-001 34.23 · `✓ Calza con: después de la diapositiva 16`.

### Diapositiva 17 — Romperlo y repararlo

Alguien borra una hora del resumen horario:

```bash
docker exec pmd-postgis psql -U postgres -c \
  "DELETE FROM resumen_horario WHERE hora = '2026-11-13 10:00-03';"
```

En `resumen_diario`: clic en el cuadrito de `verificar_horas` → ↻ → *Confirm*. Esperen ~40 s (tres intentos) y abran su log.

```bash
python3 checkpoint.py
```

> 🤔 **Antes de ejecutar:** con un `cron` a las 03:00 y un script, ¿qué habría pasado?

Ahora reparen: en `eventos_por_hora`, clic en el cuadrito de `resumir` de la ejecución de las **11:00** (la que resume la hora 10) → ↻ → *Confirm*. Cuando quede verde, de nuevo *Clear* de `verificar_horas` en `resumen_diario`.

**Resultado esperado, roto:** `verificar_horas` en rojo con `ValueError: faltan 16 filas de resumen horario del 2026-11-13`; `resumir_dia` en naranjo, sin correr · `✓ Calza con: … con la hora 10 borrada`. **Reparado:** las dos en verde · `resumen_horario` de vuelta en 96 filas (la hora 10 con `n` = 7.065) · `✓ Calza con: … o la 17 ya reparada`.

### Diapositiva 18 — n8n guarda las alertas en Postgres

En el mismo workflow de n8n, entre el **If** (salida `true`) y **Respond: alerta**, agreguen dos nodos:

| Nodo | Opción | Valor |
|---|---|---|
| **Split Out** | Fields To Split Out | `body.estaciones` |
| **Postgres** → acción *Insert or update rows in a table* | Credential | *Create new credential* (abajo) |
| | Operation | `Insert or Update` |
| | Schema / Table | `public` / `alertas` (*From list*) |
| | Columns to match on | `hora` **y** `estacion_id` |
| | Values to Send: `hora` | `{{ $('Webhook').item.json.body.hora }}` |
| | Values to Send: `estacion_id` | `{{ $json[0] }}` |
| | Values to Send: `promedio` | `{{ $json[1] }}` |

La credencial se llama **Postgres PMD**. Cambien solo dos campos; el resto viene bien por defecto (Database `postgres`, User `postgres`, Port `5432`, SSL `Disable`):

| Campo | Valor |
|---|---|
| Host | `postgres` (el nombre del servicio, no `localhost`) |
| Password | `pmd2026` |

¿Por qué `$json[0]` y `$json[1]`? Airflow manda cada estación como una lista `["CC-004", 73.85]`, no como un objeto. *Split Out* deja un ítem por estación con esa lista: la posición 0 es la estación y la 1 el promedio. La hora no viene en la lista: se la pedimos al nodo **Webhook** con `$('Webhook')`.

**Publish** de nuevo. En Airflow, clic en el cuadrito de `avisar` de las **09:00** → ↻ → marquen *Future* → *Affected Tasks: 6* → *Confirm*.

```bash
python3 checkpoint.py
docker exec pmd-postgis psql -U postgres -c "SELECT * FROM alertas ORDER BY hora;"
```

Repitan el mismo *Clear* de las seis `avisar` y vuelvan a correr `checkpoint.py`.

> 🤔 **Antes de ejecutar:** ¿por qué *Insert or Update* y no *Insert* a secas?

**Resultado esperado:** `alertas` = **6** filas, todas de CC-004: 73.04 · 73.88 · 74.19 · 74.62 · 74.54 · 73.85 (08:00 → 13:00) · `✓ Calza con: después de la diapositiva 18`. Tras el segundo *Clear*, siguen siendo **6**.

## Checkpoint

`python3 checkpoint.py` compara lo que ve con esta tabla:

| Después de… | `eventos` | `resumen_horario` filas · `sum(n)` | `resumen_diario` filas · `sum(n)` | `alertas` |
|---|---|---|---|---|
| El inicio (diap. 9–10) | 0 | 0 · 0 | 0 · 0 | 0 |
| Diap. 11 · encender con `1100` escondido | 35.294 | 80 · 35.269 | 0 · 0 | 0 |
| Diap. 12 · devolver el archivo y *Clear* de la roja | 42.368 | 96 · 42.344 | 0 · 0 | 0 |
| Diap. 13 · *Clear* de las seis | 42.368 | 96 · **42.363** | 0 · 0 | 0 |
| Diap. 16 · `resumen_diario` encendido | 42.368 | 96 · 42.363 | 16 · 42.363 | 0 |
| Diap. 17 · tras el `DELETE` de la hora 10 | 42.368 | 80 · 35.298 | 16 · 42.363 | 0 |
| Diap. 17 · reparado | 42.368 | 96 · 42.363 | 16 · 42.363 | 0 |
| Diap. 18 · alertas en Postgres | 42.368 | 96 · 42.363 | 16 · 42.363 | **6** |

Las diapositivas 14 y 15 no cambian las tablas: el avance se ve en *Executions* de n8n. Valores de control: CC-004 a las 13:00 = 73.85; en el día = 74.02.

## Si se atrasan

**En Airflow no hace falta rescate:** los DAGs ya vienen escritos. Si un paso quedó a medias, `checkpoint.py` dice dónde están; todo es idempotente, así que repetir un *Clear* no rompe nada.

**En n8n**, los workflows terminados están en `n8n/`:

1. *Create workflow* → menú **⋯** (arriba, junto al nombre) → *Import* → *From file* → `n8n/alerta_aire.json` (diap. 14) o `n8n/alerta_aire_postgres.json` (diap. 18).
2. Solo el segundo: abran el nodo **Postgres** y en *Credential* elijan «Postgres PMD» o créenla (tabla de la diap. 18). Las credenciales **no viajan** en el archivo.
3. **Publish**. Solo **un** workflow publicado puede usar la ruta `alerta-aire`: si ya tenían otro publicado, ábranlo y despublíquenlo primero (flecha junto a *Published* → *Unpublish*), o n8n reclama un conflicto de webhook.

## Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| *container name "/pmd-postgis" is already in use* | Un contenedor de otro lab: `docker rm -f pmd-postgis` (y `docker compose -f ../10/docker-compose.yml --profile bonus down -v`). |
| *all predefined address pools have been fully subnetted* | Docker se quedó sin redes: `docker network prune` borra las que no usa ningún contenedor. |
| El navegador dice *connection refused* en el 8080 | Airflow todavía arranca: `docker compose ps` hasta `healthy`. |
| El DAG no aparece | Esperen unos segundos y recarguen. Si sale un aviso rojo de *import error* arriba de la lista, el mensaje dice la línea. |
| Faltan tablas (`relation "eventos" does not exist`) | Postgres partió con un volumen viejo: `docker compose down -v` y `up -d --wait`. |
| Aparecen más o menos de 6 ejecuciones | Revisen `start_date`, `end_date` y `catchup=True` en el DAG. |
| Las ejecuciones se ven como 12:00 … 17:00 | La interfaz está en UTC: reloj de la barra izquierda → *Select Timezone* → `America/Santiago`. |
| `count` de `eventos` > 42.368 | No deduplicó: revisen la clave primaria en `sql/01_tablas.sql`. |
| `resumen_diario` suma 42.344 | Encendieron el DAG nocturno antes del *Clear* de las seis (diap. 13): *Clear* de `verificar_horas` en `resumen_diario`. |
| El *Clear* de las seis dejó roja la de las 12:00 | Hicieron el *Clear* antes de devolver el archivo: `mv escondido/eventos_1100.csv data/` y repitan. |
| El log de `avisar` dice `n8n respondió: 404 … not registered` | El workflow no está publicado (o se editó y no se volvió a publicar): **Publish**. |
| `curl` a `/webhook-test/…` da 404 | La URL de prueba solo existe mientras el lienzo espera: aprieten **Execute** antes de cada `curl`. |
| `curl` a `/webhook-test/…` da 200 vacío | Usaron *Listen for test event* dentro del nodo: prueba solo el Webhook. Usen **Execute** del lienzo. |
| El nodo Postgres falla con *null value in column "estacion_id"* | Usaron `{{ $json.estacion_id }}`: Airflow manda listas. Es `{{ $json[0] }}` y `{{ $json[1] }}`. |
| `alertas` crece con cada *Clear* | El nodo Postgres quedó en *Insert*, o con *match* por una sola columna: *Insert or Update* con `hora` **y** `estacion_id`. |
| *Publish* reclama un conflicto de webhook | Otro workflow publicado usa la misma ruta `alerta-aire`: despublíquenlo primero. |
| La máquina se arrastra | `docker stats`. Airflow solo usa ~2 GB; si hay algo del Lab 10 arriba, bájenlo. |

## Al terminar

```bash
docker compose down -v
```

Apaga todo y borra los volúmenes (`pmd11-pgdata` y `pmd11-n8ndata`): las tablas, los workflows y la credencial de n8n. Las máquinas son compartidas. Si quedó la carpeta `escondido/`, bórrenla.

## Archivos

| Archivo | Qué es |
|---|---|
| `README.md` | esta receta |
| `CONTENTS.md` | material de estudio: Airflow y n8n para quien nunca los ha usado |
| `docker-compose.yml` | Airflow + Postgres + n8n en la misma red |
| `preparar_datos.py` | copia los seis CSV de `../10/pendientes/` a `data/` y los verifica (SHA-256) |
| `checkpoint.py` | dice en qué paso calzan las cuatro tablas |
| `dags/eventos_por_hora.py` | el DAG horario: `buscar_archivo → cargar → resumir → avisar` |
| `dags/resumen_diario.py` | el DAG de las 03:00: `verificar_horas → resumir_dia` |
| `sql/01_tablas.sql` | `eventos`, `resumen_horario`, `resumen_diario` y `alertas`; las crea el compose |
| `n8n/alerta_aire.json` | el workflow de la diap. 14, para importarlo si se atrasan |
| `n8n/alerta_aire_postgres.json` | el workflow de la diap. 18 (sin la clave: la credencial se elige al importar) |
| `data/` | los seis CSV que deja `preparar_datos.py` (no se versionan) |
