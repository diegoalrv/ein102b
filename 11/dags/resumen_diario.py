from datetime import timedelta

import pendulum
from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

PG = "pmd_postgres"                      # la misma conexión del DAG horario
HORAS_DEL_DIA = 16 * 6                   # filas horarias del día: 16 estaciones × 6 horas (08:00 … 13:00)

@dag(
    schedule="0 3 * * *",                # cada noche a las 03:00
    start_date=pendulum.datetime(2026, 11, 14, 3, tz="America/Santiago"),
    end_date=pendulum.datetime(2026, 11, 14, 3, tz="America/Santiago"),
    catchup=True,                        # una sola ejecución: la noche del 13 al 14-nov
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15)},
)
def resumen_diario():

    @task
    def verificar_horas(**context):
        # la ejecución de las 03:00 del 14-nov resume el día que terminó: el 13-nov
        dia = (context["logical_date"].in_timezone("America/Santiago") - timedelta(days=1)).date()
        n = PostgresHook(postgres_conn_id=PG).get_first(
            "SELECT count(*) FROM resumen_horario "
            "WHERE (hora AT TIME ZONE 'America/Santiago')::date = %s",
            parameters=(dia,))[0]
        if n < HORAS_DEL_DIA:            # solo si terminó lo anterior: si no, resumir_dia no corre
            raise ValueError(f"faltan {HORAS_DEL_DIA - n} filas de resumen horario del {dia}")
        return dia.isoformat()

    @task
    def resumir_dia(dia):
        # promedio ponderado por n: cada hora pesa según cuántos eventos tuvo
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
