# Contenidos — Airflow y n8n: orquestar, reprocesar el pasado y avisar

**Curso:** Procesamiento Masivo de Datos (ELE051-B / EIN102B) · Paralelo 701 · 2026-2
**Bloque ETL (2 de 2) · Material de estudio del Laboratorio 11 · noviembre de 2026**

> Material de estudio del Laboratorio 11, para quien **nunca ha usado Airflow ni n8n**. Primero el modelo mental, después la interfaz pieza por pieza y al final cada línea de los dos DAGs y cada nodo del workflow. La receta paso a paso está en el [`README.md`](README.md); aquí está el porqué. Todo lo que aparece aquí salió de ensayar el lab completo contra **Airflow 3.4.0** y **n8n 2.48.6**, con los mismos datos: los nombres de menús, opciones y mensajes son los que muestran esas versiones.

---

## 1. Qué es orquestar y qué problema resuelve

La C14 terminó con una pregunta: *NiFi mueve el dato apenas llega. ¿Y si el proceso tiene que correr a las 03:00 cada noche, solo si terminó otro antes, y avisar si falla?* Son cuatro necesidades distintas, y un script con `cron` no resuelve ninguna gratis:

| Necesidad | Lo que tendría que programar a mano un script con `cron` | Lo que trae Airflow (o n8n) |
|---|---|---|
| Correr **a una hora fija** | La línea del `crontab` (esto sí es fácil) | `schedule="0 3 * * *"` |
| Saber **qué hora falló** y repetir **solo esa** | Guardar en una tabla qué horas se procesaron y cuáles fallaron, y un modo de «reprocesar la hora X» | Cada ejecución queda registrada con su hora y su estado; *Clear* la repite |
| Reintentar **sin repetir para siempre** | Un `try/except` con contador y espera | `retries=2, retry_delay=15 s` se **declaran** |
| Correr B **solo si A terminó bien** | Que B lea un archivo «bandera» que A deja al terminar | Dependencias entre tareas; entre DAGs, una tarea que verifica o un *Asset* |
| **Avisar** a alguien | Programar el correo o el mensaje, con sus credenciales | n8n: un webhook que decide y avisa, con cientos de integraciones listas |

**Orquestar** es exactamente eso: decidir **qué** corre, **cuándo**, **en qué orden**, **qué pasa si falla** y **recordar** lo que ya se hizo. El trabajo pesado (cargar 7.200 filas, agrupar) lo sigue haciendo otro: aquí, Postgres.

## 2. Airflow: el modelo mental, antes de tocar nada

Ocho palabras. Si se entienden estas, el resto es leer el DAG.

- **DAG** (*Directed Acyclic Graph*). Un conjunto de tareas con flechas entre ellas que dicen qué va antes, sin ciclos. Se escribe en Python, pero **no es un script que corre de arriba abajo**: es una **declaración** que Airflow lee para saber qué tareas hay, en qué orden y cuándo.
- **Tarea** (`@task`). Una función de Python que Airflow ejecuta como un paso. En el lab: `buscar_archivo`, `cargar`, `resumir`, `avisar`.
- **Dependencia.** «B corre después de A». Aquí sale de cómo se llaman las funciones: `avisar(resumir(cargar(buscar_archivo())))`.
- **Ejecución** (*DAG run*). Una corrida completa del DAG para **un momento**. `eventos_por_hora` tiene seis: 09:00, 10:00 … 14:00 del 13-nov.
- **Instancia de tarea** (*task instance*). Una tarea **dentro de** una ejecución: «`resumir` de la ejecución de las 11:00». Es la unidad que tiene estado, log y reintentos. 6 ejecuciones × 4 tareas = 24 instancias.
- ***Logical date*.** La hora que una ejecución **representa**, no la hora real en que corrió. Las seis ejecuciones del lab corrieron el 20-nov en un minuto, pero sus *logical dates* son 13-nov 09:00 … 14:00.
- **Estados.** `queued` (en cola, esperando turno), `running`, `success` (verde), `failed` (rojo: falló después de agotar los reintentos), `upstream_failed` (naranjo: no corrió porque una tarea anterior falló), `up_for_retry` (falló, pero le quedan reintentos).
- **Reintento.** Si una tarea falla y le quedan intentos, Airflow espera `retry_delay` y la vuelve a correr. `retries=2` = hasta 3 intentos.

`eventos_por_hora`, con cada término señalado:

```text
            DAG «eventos_por_hora»  (schedule = cada hora en punto)
            ──────────────────────────────────────────────────────────────────▶ logical date
              09:00         10:00         11:00         12:00         13:00         14:00
            ┌───────┐     ┌───────┐     ┌───────┐     ┌───────┐     ┌───────┐     ┌───────┐
 tarea →    │buscar │     │buscar │     │buscar │     │buscar ✗│    │buscar │     │buscar │  ← instancia de tarea
   │        │cargar │     │cargar │     │cargar │     │cargar ▲│    │cargar │     │cargar │     (rojo: failed)
dependencia │resumir│     │resumir│     │resumir│     │resumir▲│    │resumir│     │resumir│  ← naranjo: upstream_failed
   ▼        │avisar │     │avisar │     │avisar │     │avisar ▲│    │avisar │     │avisar │
            └───────┘     └───────┘     └───────┘     └───────┘     └───────┘     └───────┘
             ejecución     ejecución                  la de las 12:00 busca eventos_1100.csv
            (DAG run)                                 y no lo encuentra (diap. 11)
```

**Las piezas por dentro.** Airflow no es un programa, son cuatro procesos que comparten una base de datos:

| Pieza | Qué hace |
|---|---|
| ***dag-processor*** | Lee los archivos de `dags/` cada pocos segundos y guarda en la base qué DAGs y tareas hay. Si un archivo tiene un error, lo informa (*Dag Import Errors*). |
| ***scheduler*** | Mira la base y decide qué toca: crea las ejecuciones que faltan, pone en cola las tareas cuyas dependencias terminaron, programa los reintentos. |
| ***executor* / *workers*** | Ejecutan las tareas. En el lab, procesos locales del mismo contenedor. |
| ***api-server*** | La interfaz web y la API REST (puerto 8080). La interfaz solo **muestra** y **pide**: no ejecuta nada. |
| **base de metadatos** | Recuerda el estado de cada instancia de tarea de cada ejecución. **Por eso Airflow sabe qué falló.** |

`airflow standalone` (el `command:` del compose) junta todo eso en un contenedor, con SQLite como base de metadatos. Es **solo para desarrollo**: en producción, cada pieza va por separado y la base es Postgres.

## 3. La interfaz de Airflow, pieza por pieza

La interfaz sale en el idioma del navegador; aquí van los nombres en inglés y, entre comillas, en español cuando ayuda.

- **Lista de DAGs** (*Dags*, en la barra izquierda). Una fila por DAG, con su **interruptor** de pausa: apagado = el *scheduler* no crea ejecuciones. Los dos DAGs del lab parten **apagados** (en Airflow, un DAG nuevo parte pausado por defecto).
- **La página de un DAG.** Arriba: programación, última y siguiente ejecución, y el interruptor (arriba a la derecha). Abajo, pestañas: *Overview*, *Runs* (las ejecuciones en tabla), *Tasks*, *Code* (el archivo `.py` tal como lo leyó Airflow), etc.
- **Vista *Grid*** (el panel de la izquierda; tecla `g` alterna con *Graph*). **Columnas = ejecuciones** (la más nueva a la derecha), **filas = tareas**. Cada cuadrito es una instancia de tarea, con el color de su estado. Es la vista que más van a usar.
- **Vista *Graph*.** Las tareas como cajas con flechas: la forma del DAG.
- **El log de una tarea.** Clic en un cuadrito → pestaña *Logs*. Arriba, *Task Tries* («Intentos de Tarea»): un botón por intento, para ver el log de cada uno. Ahí aparece lo que la tarea imprime con `print` y la traza del error si falló.
- ***Clear*** («Limpiar»). En la página de una instancia de tarea, el botón ↻ arriba a la derecha (atajo `shift+c`). Abre *Clear Task Instance* con estas opciones:
  - *Downstream*: también las tareas que dependen de esta (viene marcado). *Upstream*: también las anteriores.
  - *Past* / *Future*: la misma tarea en las ejecuciones **anteriores** / **posteriores**. Desde la ejecución de las 09:00 con *Future* se limpian las seis.
  - *Only Failed* («Limpiar solo tareas fallidas»): solo las que están en rojo.
  - *Affected Tasks: N*: cuántas instancias va a limpiar. **Mírenlo antes de confirmar.**
  - *Confirm*: las instancias vuelven a `queued` y el *scheduler* las corre de nuevo, respetando las dependencias.
- **Errores de importación.** Si un archivo de `dags/` no se puede leer, aparece un aviso rojo (*Dag Import Errors*) con el archivo y la línea.
- **La zona horaria.** El reloj de la barra izquierda (abajo) muestra la zona en uso (`-03:00`). Por defecto es la del navegador. Clic → *Select Timezone*.

## 4. Los dos DAGs, línea por línea

### 4.1. `eventos_por_hora`: la cabecera

```python
import csv
from datetime import timedelta

import pendulum
import requests
from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

DATOS = "/opt/airflow/data"
PG = "pmd_postgres"                      # conexión definida en el compose
```

- `pendulum`: la biblioteca de fechas que usa Airflow; sus fechas siempre llevan zona horaria.
- `requests`: para llamar a n8n por HTTP.
- `from airflow.sdk import dag, task`: en Airflow 3, todo lo que se usa para **escribir** DAGs viene de `airflow.sdk`.
- `PostgresHook`: un objeto que sabe conectarse a Postgres a partir de una **conexión** de Airflow, por su nombre.
- `DATOS`: la ruta **de adentro** del contenedor (en su máquina es `./data`).
- `PG = "pmd_postgres"`: el nombre de la conexión. No hay clave en el DAG: el compose define la variable `AIRFLOW_CONN_PMD_POSTGRES=postgresql://postgres:pmd2026@postgres:5432/postgres`, y Airflow arma la conexión `pmd_postgres` a partir de ella (todo lo que viene después de `AIRFLOW_CONN_`, en minúsculas).

```python
@dag(
    schedule="0 * * * *",                # cada hora en punto
    start_date=pendulum.datetime(2026, 11, 13, 9, tz="America/Santiago"),
    end_date=pendulum.datetime(2026, 11, 13, 14, tz="America/Santiago"),
    catchup=True,                        # en Airflow 3 el default es False
    max_active_runs=1,                   # una hora a la vez, en orden
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
)
def eventos_por_hora():
```

- `@dag`: convierte la función en un DAG. El nombre del DAG es el de la función.
- `schedule="0 * * * *"`: expresión *cron* (minuto, hora, día, mes, día de la semana): «en el minuto 0 de cada hora».
- `start_date` / `end_date`: el rango de *logical dates* que existe. Con `end_date` = 14:00 hay **6** ejecuciones (09:00 … 14:00); sin él, Airflow crearía una por cada hora desde el 13-nov hasta ahora (más de 160).
- `catchup=True`: al encender el DAG, crear **todas** las ejecuciones pendientes del pasado. En Airflow 3 viene apagado: sin esta línea, solo aparece la más reciente.
- `max_active_runs=1`: una ejecución a la vez, en orden. Sin esto, las seis corren en paralelo y los resúmenes salen distintos (la hora 11 vería o no sus tardíos según quién llegue primero).
- `default_args`: argumentos que reciben **todas** las tareas. `retries=2` con 15 s entre intentos.

### 4.2. Las cuatro tareas

```python
    @task
    def buscar_archivo(**context):
        # la ejecución de las 09:00 procesa la hora que terminó: 08:00–08:59
        hora = context["logical_date"].in_timezone("America/Santiago") - timedelta(hours=1)
        ruta = f"{DATOS}/eventos_{hora:%H}00.csv"
        open(ruta).close()               # si no está, falla y Airflow reintenta
        return {"ruta": ruta, "hora": hora.isoformat()}
```

- `**context`: Airflow le pasa a la tarea un diccionario con todo lo que sabe de la ejecución. Aquí se usa `logical_date`.
- `in_timezone(...)`: la *logical date* viene en UTC; se pasa a hora de Chile para armar el nombre del archivo.
- `- timedelta(hours=1)`: la ejecución de las 09:00 procesa la hora que **terminó** (08:00–08:59), así que busca `eventos_0800.csv`. En Airflow 3, con un `schedule` cron, la *logical date* es el momento en que la ejecución corre (09:00); por eso hay que restar una hora. (En el ensayo: la primera ejecución tiene *logical date* 13-nov 09:00 hora de Chile.)
- `open(ruta).close()`: solo comprueba que el archivo exista. Si no, `FileNotFoundError` → la tarea falla → Airflow reintenta.
- `return {...}`: lo que devuelve una tarea se guarda como **XCom** y se lo pasa a la siguiente. Aquí, una ruta y una hora: unos pocos bytes.

```python
    @task
    def cargar(archivo):
        with open(archivo["ruta"]) as f:
            filas = [(r["estacion_id"], r["tipo_sensor"], float(r["valor"]), r["ts"])
                     for r in csv.DictReader(f)]
        with PostgresHook(postgres_conn_id=PG).get_conn() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO eventos VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", filas)
        return archivo
```

- `archivo`: el diccionario que devolvió `buscar_archivo` (Airflow lo saca del XCom).
- `csv.DictReader`: lee el CSV fila por fila como diccionarios (`r["valor"]`, …).
- `get_conn()`: una conexión a Postgres. El `with` hace *commit* al salir sin error. (En la imagen del lab, el *hook* usa el driver `psycopg` 3.)
- `executemany(...)`: el mismo `INSERT` para cada fila, con los valores en los `%s`.
- `ON CONFLICT DO NOTHING`: si la clave `(estacion_id, ts)` ya existe, la fila se salta. Es el mismo `INSERT_IGNORE` de la C14: los repetidos del generador se descartan y repetir la tarea no duplica nada. 7.200 filas → 7.063 en la tabla.

```python
    @task
    def resumir(archivo):
        PostgresHook(postgres_conn_id=PG).run("""
            INSERT INTO resumen_horario (hora, estacion_id, tipo_sensor, n, promedio)
            SELECT date_trunc('hour', ts), estacion_id, tipo_sensor, count(*), avg(valor)
            FROM eventos
            WHERE ts >= %(h)s AND ts < %(h)s::timestamptz + interval '1 hour'
            GROUP BY 1, 2, 3
            ON CONFLICT (hora, estacion_id) DO UPDATE
              SET n = EXCLUDED.n, promedio = EXCLUDED.promedio""",
            parameters={"h": archivo["hora"]})
        return archivo["hora"]
```

- `run(sql, parameters=...)`: ejecuta una sentencia SQL; `%(h)s` se reemplaza por `archivo["hora"]`.
- `INSERT … SELECT`: el resumen lo calcula **Postgres**, no Python. Airflow solo le dice qué hora.
- `WHERE ts >= h AND ts < h + 1 hora`: se resume por la **columna `ts`**, no por el archivo. Los eventos de la hora 08 que llegaron en `eventos_0900.csv` también cuentan… si ya estaban en la tabla al momento de resumir.
- `ON CONFLICT (hora, estacion_id) DO UPDATE`: si la fila del resumen ya existe, se **reemplaza** con los números nuevos (`EXCLUDED` = la fila que se intentó insertar). Repetir `resumir` corrige el resumen; nunca lo suma dos veces.

```python
    @task
    def avisar(hora):
        altos = PostgresHook(postgres_conn_id=PG).get_records(
            "SELECT estacion_id, round(promedio::numeric, 2)::float FROM resumen_horario "
            "WHERE hora = %s AND tipo_sensor = 'calidad_aire' AND promedio > 70",
            parameters=(hora,))
        try:
            r = requests.post("http://n8n:5678/webhook/alerta-aire",
                              json={"hora": hora, "estaciones": altos}, timeout=5)
            print("n8n respondió:", r.status_code, r.text)
        except requests.RequestException as e:
            print("n8n no respondió:", e)     # el aviso no debe botar el DAG
```

- `get_records`: una lista de filas. Cada fila es una **lista** `[estacion_id, promedio]`: `[["CC-004", 73.85]]`. (Esto importa en n8n, sección 8.)
- `http://n8n:5678`: n8n por el nombre del servicio, dentro de la red del compose.
- `timeout=5`: si n8n no contesta en 5 s, se rinde.
- `try / except`: si n8n está caído, la tarea solo deja una línea en el log y termina en verde. **El aviso nunca bota el DAG.** Si n8n está arriba pero el workflow no está publicado, n8n contesta igual, con un 404: el log dice `n8n respondió: 404 … not registered`.

```python
    avisar(resumir(cargar(buscar_archivo())))

eventos_por_hora()
```

- La primera línea **declara** la cadena: lo que devuelve cada tarea es la entrada de la siguiente, y eso le dice a Airflow el orden.
- `eventos_por_hora()`: crea el DAG. Sin esta línea, Airflow no ve nada.

### 4.3. `resumen_diario`: el DAG de las 03:00

```python
PG = "pmd_postgres"                      # la misma conexión del DAG horario
FILAS_DEL_DIA = 16 * 6                   # 16 estaciones × 6 horas (08:00 … 13:00) de eventos_por_hora

@dag(
    schedule="0 3 * * *",                # cada noche a las 03:00
    start_date=pendulum.datetime(2026, 11, 14, 3, tz="America/Santiago"),
    end_date=pendulum.datetime(2026, 11, 14, 3, tz="America/Santiago"),
    catchup=True,                        # una sola ejecución: la noche del 13 al 14-nov
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
)
def resumen_diario():
```

- `"0 3 * * *"`: a las 03:00 de cada día.
- `start_date` = `end_date` = 14-nov 03:00: existe **una** ejecución, la que resume el 13-nov.

```python
    @task
    def verificar_horas(**context):
        dia = (context["logical_date"].in_timezone("America/Santiago") - timedelta(days=1)).date()
        filas = PostgresHook(postgres_conn_id=PG).get_first(
            "SELECT count(*) FROM resumen_horario "
            "WHERE (hora AT TIME ZONE 'America/Santiago')::date = %s",
            parameters=(dia,))[0]
        if filas < FILAS_DEL_DIA:        # falla: resumir_dia no corre (upstream_failed)
            raise ValueError(f"faltan {FILAS_DEL_DIA - filas} filas de resumen horario del {dia}")
        return dia.isoformat()
```

- `- timedelta(days=1)`: la ejecución de las 03:00 del 14-nov resume el día que terminó, el 13-nov.
- `hora AT TIME ZONE 'America/Santiago'`: pasa la hora a hora de Chile antes de sacarle la fecha (si no, las horas cerca de medianoche caerían en el día equivocado).
- `get_first`: la primera fila del resultado; `[0]`, su primera columna.
- `raise ValueError(...)`: **esta es la dependencia «solo si terminó lo anterior»**. Si `eventos_por_hora` no dejó las 96 filas, la tarea falla, Airflow reintenta dos veces (por si el otro DAG solo iba atrasado) y, si sigue faltando, queda roja y `resumir_dia` queda en naranjo sin correr. Nadie recibe un resumen de un día incompleto.

```python
    @task
    def resumir_dia(dia):
        PostgresHook(postgres_conn_id=PG).run("""
            INSERT INTO resumen_diario (dia, estacion_id, tipo_sensor, n, promedio)
            SELECT %(d)s::date, estacion_id, tipo_sensor, sum(n), sum(n * promedio) / sum(n)
            FROM resumen_horario
            WHERE (hora AT TIME ZONE 'America/Santiago')::date = %(d)s::date
            GROUP BY 2, 3
            ON CONFLICT (dia, estacion_id) DO UPDATE
              SET n = EXCLUDED.n, promedio = EXCLUDED.promedio""",
            parameters={"d": dia})

    resumir_dia(verificar_horas())

resumen_diario()
```

- `sum(n * promedio) / sum(n)`: el **promedio ponderado**. Cada hora pesa según cuántos eventos tuvo. Promediar los seis promedios horarios daría a cada hora el mismo peso aunque una tenga más eventos que otra.
  Ejemplo con CHI-001: ponderado **65.73**, promedio simple de los seis promedios **65.77**. (En CC-004 los dos dan 74.02 por casualidad: no sirve de ejemplo.)
- `ON CONFLICT … DO UPDATE`: igual que en `resumir`; repetir el DAG nocturno reemplaza, no suma.

## 5. El tiempo en Airflow

- ***Logical date* contra hora real.** La ejecución «de las 12:00» del 13-nov corrió el 20-nov. Lo que importa para el procesamiento es la *logical date*; la hora real queda en el log y en la base.
- ***Catchup*.** Al encender un DAG, Airflow crea las ejecuciones que «debieron» existir entre `start_date` y ahora (o `end_date`). Por eso aparecen seis de golpe.
- ***Backfill*.** Reprocesar **a propósito** un rango del pasado (por ejemplo, después de corregir un error). En el lab lo hacemos con *Clear*; Airflow también tiene una pestaña *Backfills* para crear ejecuciones de un rango.
- **Idempotencia.** Correr una tarea dos veces deja lo mismo que correrla una. Es lo que hace seguro el *Clear*: `cargar` (con `DO NOTHING`) y `resumir` (con `DO UPDATE`) se pueden repetir sin daño. Es la misma idea de la C14: NiFi pedía destinos idempotentes; Airflow pide **tareas** idempotentes.
- **Datos tardíos.** Que «la hora terminó» no significa que «llegaron todos sus datos». En el lab, `eventos_0900.csv` trae eventos con `ts` de las 08:59. Cuando la ejecución de las 09:00 resumió la hora 08, esos eventos todavía no estaban en la tabla: el resumen quedó corto. Los números:
  - Después de reparar la hora 11 (diap. 12): `eventos` = 42.368, pero la suma de los resúmenes = **42.344**. Faltan 24.
  - En total hay **26 tardíos** entre las horas 08 y 12 (5 · 3 · 6 · 7 · 5). La hora 11 se reprocesó al final (diap. 12) y ya vio sus 7; por eso faltan 24 y no 26.
  - *Clear* de las seis → **42.363**. Quedan **5** sin resumir: tienen `ts` en la hora **07**, antes del `start_date`, y ninguna ejecución cubre esa hora.
- **Tres estrategias para los tardíos** (son decisiones de negocio, no técnicas):
  1. **Reprocesar las últimas N horas** cada vez (cada ejecución vuelve a resumir también la hora anterior).
  2. **Resumir con margen:** la hora 08 se resume a las 09:15, no a las 09:00.
  3. **Aceptar el error y documentarlo:** «los resúmenes pueden subestimar hasta un 0,1 %».

## 6. Dependencias entre DAGs

`resumen_diario` depende de `eventos_por_hora`, pero son DAGs distintos. Tres maneras de expresarlo (en el lab usamos la primera; las otras dos solo se explican):

- **La casera (la del lab):** una tarea que **verifica el resultado** del otro DAG (`verificar_horas` cuenta filas). Ventaja: verifica lo que importa (los datos), no solo que el otro DAG «terminó».
- ***Assets*:** la tarea productora declara `outlets=[Asset("resumen_horario")]` y el DAG consumidor usa `schedule=[Asset("resumen_horario")]`: corre cada vez que el *asset* se actualiza.
- **`ExternalTaskSensor`:** una tarea que **espera** a que una tarea de otro DAG, de la misma *logical date*, termine en verde.

## 7. n8n: el modelo mental

n8n se parece a NiFi a primera vista (cajas y flechas), pero piensa distinto: NiFi es un flujo que corre siempre; en n8n **cada ejecución parte por un evento y recorre el workflow una vez**.

- **Disparador** (*trigger*). El primer nodo: lo que hace partir una ejecución. Un *Webhook* (llega una llamada HTTP), un horario, un correo, un formulario.
- **Nodo.** Una caja que hace una cosa: decidir (*If*), responder (*Respond to Webhook*), escribir en Postgres.
- **Ítem.** n8n procesa **listas de ítems**: cada nodo recibe una lista y entrega otra. Cada ítem es un objeto JSON. Un nodo corre una vez **por ítem** (por eso *Split Out* convierte una lista en varios ítems).
- **Expresiones** `{{ }}`. Todo lo que va entre `{{ }}` es JavaScript que se evalúa para cada ítem. `$json` es el ítem actual; `$('Webhook')` es la salida del nodo llamado Webhook; `.item` es «el ítem de ese nodo que corresponde al actual» (*paired items*: n8n recuerda de qué ítem salió cada uno).
- **URL de prueba contra URL de producción.** El Webhook tiene dos: `/webhook-test/alerta-aire` existe solo mientras el editor está esperando (botón **Execute**), para **una** llamada; `/webhook/alerta-aire` existe solo si el workflow está **publicado**.
- **Borrador y publicado.** En n8n 2.x ya no hay interruptor *Active*: un workflow se edita como borrador y se **publica** (*Publish*). Los cambios posteriores no llegan a producción hasta volver a publicar.
- ***Executions*.** La pestaña con cada ejecución que hubo: qué llegó, qué hizo cada nodo, dónde falló. Las llamadas a la URL de producción **no** se ven en el lienzo: solo aquí.
- **Credenciales.** Las claves (la de Postgres) se guardan aparte, cifradas, y los nodos las referencian por nombre. **No viajan** cuando se exporta un workflow (*Export JSON*): al importarlo hay que elegir o crear la credencial.

## 8. Los nodos del lab, uno por uno

- **Webhook.** Recibe la llamada HTTP de Airflow. *HTTP Method* `POST` (Airflow manda datos); *Path* `alerta-aire` (la última parte de la URL); *Respond* `Using 'Respond to Webhook' Node`: la respuesta la decide un nodo más adelante (si no, n8n respondería apenas llega la llamada, sin saber si hay alerta). Lo que llegó queda en el ítem como `body`, junto con `headers` y `query`: por eso la lista es `$json.body.estaciones`.
- **If.** Divide los ítems en dos salidas, `true` y `false`, según una condición. Aquí: `{{ $json.body.estaciones.length }}` (cuántas estaciones vienen) con el operador *Number → is greater than* `0`.
- **Respond to Webhook.** Contesta la llamada que recibió el Webhook. *Respond With* `JSON` y el cuerpo fijo `{"alerta": true}` (o `false`). Responde **una** vez por ejecución.
- **Split Out.** Toma un campo que es una lista y entrega **un ítem por elemento**. *Fields To Split Out* `body.estaciones`. Como cada estación viene como lista (`["CC-004", 73.85]`, sección 4.2), cada ítem queda así: `{"0": "CC-004", "1": 73.85}`. Por eso después se usa `$json[0]` y `$json[1]`.
- **Postgres.** *Operation* `Insert or Update` (*upsert*): inserta la fila o, si ya existe una con la misma clave, la actualiza. *Columns to match on* `hora` **y** `estacion_id`: las mismas dos columnas de la clave primaria de `alertas`. Los valores: `hora` = `{{ $('Webhook').item.json.body.hora }}` (la hora no está en el ítem de *Split Out*: se la pedimos al Webhook), `estacion_id` = `{{ $json[0] }}`, `promedio` = `{{ $json[1] }}`. Con *Insert* a secas, el segundo *Clear* de `avisar` fallaría por la clave primaria; con *match* por una sola columna, la tabla crecería.

## 9. NiFi, Airflow o n8n

| | NiFi | Airflow | n8n |
|---|---|---|---|
| Modelo mental | **flujo continuo**: el dato llega y se mueve ya | **lotes con calendario**: tareas con orden, horario y memoria | **eventos**: «cuando pase X, haz Y» |
| Qué viaja | el dato (FlowFiles) | casi nada (XCom: valores chicos); el dato va directo a la base | ítems JSON chicos |
| Si algo falla | cola + reintentos + carpeta de errores | reintentos + estado por ejecución + *Clear* | la ejecución queda en rojo en *Executions* |
| Los seis CSV del lab | un flujo que toma cada archivo apenas aparece | una ejecución por hora, aunque el archivo no esté | (no es para esto) |

Cómo elegir: ¿el dato llega sin parar y hay que moverlo entre sistemas? → NiFi. ¿Hay pasos en orden, con horario, reintentos y reproceso del pasado? → Airflow. ¿Algo externo dispara una acción liviana? → n8n. Si dudan: un **script** primero, y una herramienta cuando duela.

## 10. Errores frecuentes

| Lo que se ve | La causa |
|---|---|
| `FileNotFoundError: … /opt/airflow/data/eventos_1100.csv` en `buscar_archivo` | El archivo no está en `data/` (en la diap. 11, a propósito). |
| Aviso rojo *Dag Import Errors* | Un error de Python en un archivo de `dags/`: el mensaje dice la línea. |
| Aparece 1 ejecución en vez de 6 | Falta `catchup=True` (en Airflow 3 viene apagado). |
| `n8n respondió: 404 {"code":404,"message":"The requested webhook \"POST alerta-aire\" is not registered." …}` | El workflow no está publicado. |
| `curl` a `/webhook-test/…` responde `404 … is not registered` con la pista *Click the 'Execute workflow' button* | La URL de prueba solo existe después de apretar **Execute**, para una llamada. |
| `null value in column "estacion_id" of relation "alertas" violates not-null constraint` | En el nodo Postgres se usó `$json.estacion_id`: Airflow manda listas, es `$json[0]`. |
| *There is a conflict with one of the webhooks* al publicar | Otro workflow publicado ya usa la ruta `alerta-aire`. |
| `ValueError: faltan 16 filas de resumen horario del 2026-11-13` | `resumen_horario` no tiene las 96 filas del día: alguna hora falta o falló (diap. 17, a propósito). |

## 11. Puente al proyecto

No es obligatorio usar NiFi, Airflow ni n8n en el proyecto; **sí** cruzar ≥ 2 familias de bases. Si usan una de estas herramientas:

- tiene que levantar con `docker compose up`, como hoy, y el repo tiene que explicar cómo;
- tiene que justificarse con **una de sus ≥ 5 preguntas**: «la pregunta 3 necesita datos de cada noche → un DAG a las 03:00»; «la pregunta 5 depende de un evento externo → un webhook».

Si ninguna pregunta lo pide, un script basta.
