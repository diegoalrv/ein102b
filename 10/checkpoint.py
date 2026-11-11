"""Laboratorio 10 — ¿en qué paso estoy y está bien?

    python3 checkpoint.py           # Postgres, Redis y las carpetas
    python3 checkpoint.py --bonus   # ... y además Neo4j

Consulta los contenedores con `docker exec` (no necesita ningún paquete de Python) y busca
en qué paso de la receta calza lo que ve. Se puede correr cuantas veces quieran: solo lee.
"""
import subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).parent

# (después de…, filas en Postgres, DBSIZE de Redis, sensor:CC-004 valor, ts)
# Postgres None = está caído a propósito (diap. 12): no se puede consultar.
ESTADOS = [
    ("el inicio, sin nada cargado (diapositivas 5 a 9)", 0, 0, None, None),
    ("la diapositiva 10 (archivo de las 08:00, copiado de nuevo)", 7063, 0, None, None),
    ("el rescate importado, con el archivo de las 08:00 (sigan en la diapositiva 11)", 7063, 16, "64.2",
     "2026-11-13T08:59:47.000-03:00"),
    ("la diapositiva 11 (archivo de las 09:00)", 14100, 16, "69.8", "2026-11-13T09:59:53.500-03:00"),
    ("la diapositiva 12, con Postgres caído (tras los tres cp)", None, 16, "77.3", "2026-11-13T10:59:57.500-03:00"),
    ("la diapositiva 12, con Postgres de vuelta", 35310, 16, "80.0", "2026-11-13T12:59:55.500-03:00"),
    ("la diapositiva 13 (reenvío del archivo de las 08:00)", 35310, 16, "64.2", "2026-11-13T08:59:47.000-03:00"),
    ("el bonus, con el archivo de las 13:00", 42368, 16, "70.3", "2026-11-13T13:59:42.500-03:00"),
]


def docker(contenedor, *cmd):
    """Salida del comando dentro del contenedor, o None si el contenedor no responde."""
    try:
        r = subprocess.run(["docker", "exec", contenedor, *cmd], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def mismo_instante(guardado, esperado):
    """El ts de Redis puede quedar como texto ISO, con otro formato o en milisegundos: se compara el instante."""
    if guardado is None or esperado is None:
        return guardado == esperado
    objetivo = datetime.fromisoformat(esperado)
    if guardado.lstrip("-").isdigit():
        return int(guardado) == int(objetivo.timestamp() * 1000)
    try:
        t = datetime.fromisoformat(guardado.replace(" ", "T"))
    except ValueError:
        return False
    if t.tzinfo is None:          # sin zona: se supone la hora de Concepción del lab o UTC
        return t in (objetivo.replace(tzinfo=None), objetivo.astimezone().replace(tzinfo=None),
                     datetime.fromtimestamp(objetivo.timestamp(), timezone.utc).replace(tzinfo=None))
    return t == objetivo


def contar(carpeta):
    return sum(1 for p in (AQUI / carpeta).iterdir() if not p.name.startswith("."))


def principal():
    pg = docker("pmd-postgis", "psql", "-U", "postgres", "-tAc", "SELECT count(*) FROM eventos")
    dbsize = docker("pmd-redis", "redis-cli", "DBSIZE")
    valor = docker("pmd-redis", "redis-cli", "HGET", "sensor:CC-004", "valor") or None
    ts = docker("pmd-redis", "redis-cli", "HGET", "sensor:CC-004", "ts") or None
    errores, entrada = contar("errores"), contar("entrada")

    print(f"Postgres  eventos        {pg if pg is not None else '— (pmd-postgis no está corriendo)'}")
    print(f"Redis     DBSIZE         {dbsize if dbsize is not None else '— (pmd-redis no está corriendo)'}")
    print(f"Redis     sensor:CC-004  valor = {valor or '—'} · ts = {ts or '—'}")
    print(f"Carpetas  errores/ = {errores} · entrada/ = {entrada}")
    if dbsize is None:
        return False

    pg_n = int(pg) if pg is not None and pg.isdigit() else None
    for nombre, e_pg, e_db, e_valor, e_ts in ESTADOS:
        if (pg_n == e_pg and int(dbsize) == e_db and errores == 0
                and (valor == e_valor if e_valor else valor is None) and mismo_instante(ts, e_ts)):
            print(f"\n✓ Calza con: {'' if nombre.startswith('el ') else 'después de '}{nombre}")
            return True

    print("\n✗ No calza con ningún paso de la receta. Pistas:")
    if pg_n == 7200:
        print("  · Postgres tiene 7.200: no deduplicó. Revisen Statement Type = INSERT_IGNORE y la clave primaria (\\d eventos).")
    if pg_n is not None and pg_n % 7200 == 0 and pg_n > 7200:
        print("  · Postgres es múltiplo de 7.200: no está deduplicando. Revisen Statement Type = INSERT_IGNORE.")
    if errores:
        print("  · Hay archivos en errores/: abran el bulletin (cuadrito rojo) de PutDatabaseRecord.")
    if pg_n is not None and pg_n >= 14100 and int(dbsize) == 0:
        print("  · Redis está vacío: revisen el Hash Value Record Path (/clave) y que los servicios estén Enabled.")
    if pg is None:
        print("  · pmd-postgis no está corriendo: si no lo botaron a propósito, docker compose up -d --wait.")
    if entrada == 0 and pg_n == 0:
        print("  · entrada/ está vacía: copien el archivo de la hora (cp pendientes/eventos_HH00.csv entrada/).")
    print("  · Si recién copiaron un archivo, esperen unos 10 s (ListFile mira cada 5 s) y vuelvan a correrlo.")
    return False


def bonus():
    q = lambda c: docker("pmd-neo4j", "cypher-shell", "-u", "neo4j", "-p", "pmd2026neo", "--format", "plain", c)
    sensores = q("MATCH (s:Sensor) RETURN count(s)")
    if sensores is None:
        print("\nNeo4j     — (pmd-neo4j no está corriendo: docker compose --profile bonus up -d --wait)")
        return False
    en = q("MATCH (:Sensor)-[r:EN]->(:Comuna) RETURN count(r)").splitlines()[-1]
    cc = q("MATCH (s:Sensor {id: 'CC-004'}) RETURN s.n, round(s.promedio, 2)").splitlines()
    cc = cc[-1] if len(cc) > 1 else "—"
    filas = q("MATCH (s:Sensor {tipo: 'calidad_aire'})-[:EN]->(c:Comuna)<-[:EN]-(p:Parada) "
              "WHERE s.promedio > 60 RETURN c.nombre AS comuna, collect(p.nombre) AS paradas").splitlines()[1:]
    sensores = sensores.splitlines()[-1]
    print(f"\nNeo4j     Sensor = {sensores} · EN desde Sensor = {en} · CC-004 (n, promedio) = {cc} · "
          f"consulta de la diap. 13 = {len(filas)} filas")
    ok = (sensores, en, cc, len(filas)) == ("16", "16", "464, 73.84", 3)
    print("✓ El bonus calza" if ok else
          "✗ El bonus no calza: miren el LogAttribute de InvokeHTTP (Log Payload) y busquen «errors».")
    return ok


if __name__ == "__main__":
    ok = principal()
    if "--bonus" in sys.argv:
        ok = bonus() and ok
    sys.exit(0 if ok else 1)
