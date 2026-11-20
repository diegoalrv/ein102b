import csv
from datetime import timedelta

import pendulum
import requests
from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

DATOS = "/opt/airflow/data"
PG = "pmd_postgres"                      # conexión definida en el compose

@dag(
    schedule="0 * * * *",                # cada hora en punto
    start_date=pendulum.datetime(2026, 11, 13, 9, tz="America/Santiago"),
    end_date=pendulum.datetime(2026, 11, 13, 14, tz="America/Santiago"),
    catchup=True,                        # en Airflow 3 el default es False
    max_active_runs=1,                   # una hora a la vez, en orden
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
)
def eventos_por_hora():

    @task
    def buscar_archivo(**context):
        # la ejecución de las 09:00 procesa la hora que terminó: 08:00–08:59
        hora = context["logical_date"].in_timezone("America/Santiago") - timedelta(hours=1)
        ruta = f"{DATOS}/eventos_{hora:%H}00.csv"
        open(ruta).close()               # si no está, falla y Airflow reintenta
        return {"ruta": ruta, "hora": hora.isoformat()}

    @task
    def cargar(archivo):
        with open(archivo["ruta"]) as f:
            filas = [(r["estacion_id"], r["tipo_sensor"], float(r["valor"]), r["ts"])
                     for r in csv.DictReader(f)]
        with PostgresHook(postgres_conn_id=PG).get_conn() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO eventos VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", filas)
        return archivo

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

    @task
    def avisar(hora):
        altos = PostgresHook(postgres_conn_id=PG).get_records(
            "SELECT estacion_id, round(promedio::numeric, 2)::float FROM resumen_horario "
            "WHERE hora = %s AND tipo_sensor = 'calidad_aire' AND promedio > 70",
            parameters=(hora,))
        try:
            r = requests.post("http://n8n:5678/webhook/alerta-aire",
                              json={"hora": hora, "estaciones": [
                                  {"estacion_id": e, "promedio": p} for e, p in altos]},
                              timeout=5)
            print("n8n respondió:", r.status_code, r.text)
        except requests.RequestException as e:
            print("n8n no respondió:", e)     # el aviso no debe botar el DAG

    avisar(resumir(cargar(buscar_archivo())))

eventos_por_hora()
