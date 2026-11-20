"""Laboratorio 11 — ¿en qué paso estoy y está bien?

    python3 checkpoint.py

Consulta Postgres con `docker exec` (no necesita ningún paquete de Python) y busca en qué
paso de la receta calzan las cuatro tablas. Se puede correr cuantas veces quieran: solo lee.
"""
import subprocess, sys

CONSULTA = """SELECT
  (SELECT count(*) FROM eventos),
  (SELECT count(*) FROM resumen_horario), (SELECT coalesce(sum(n), 0) FROM resumen_horario),
  (SELECT count(*) FROM resumen_diario),  (SELECT coalesce(sum(n), 0) FROM resumen_diario),
  (SELECT count(*) FROM alertas),
  (SELECT round(promedio::numeric, 2) FROM resumen_horario
    WHERE estacion_id = 'CC-004' AND hora = '2026-11-13 13:00-03'),
  (SELECT round(promedio::numeric, 2) FROM resumen_diario WHERE estacion_id = 'CC-004')"""

# (después de…, eventos, resumen_horario filas, sum(n), resumen_diario filas, sum(n), alertas)
ESTADOS = [
    ("el inicio (diapositivas 9 y 10)", 0, 0, 0, 0, 0, 0),
    ("la diapositiva 11 (encendido con 1100 escondido: 5 verdes, 1 roja)", 35294, 80, 35269, 0, 0, 0),
    ("la diapositiva 12 (archivo devuelto y Clear de la roja)", 42368, 96, 42344, 0, 0, 0),
    ("la diapositiva 13 (Clear de las seis). Si están en n8n (diap. 14 y 15), "
     "las tablas no cambian: el avance se ve en Executions", 42368, 96, 42363, 0, 0, 0),
    ("la diapositiva 16 (resumen_diario encendido), o la 17 ya reparada", 42368, 96, 42363, 16, 42363, 0),
    ("la diapositiva 17, con la hora 10 borrada (verificar_horas tiene que quedar en rojo)",
     42368, 80, 35298, 16, 42363, 0),
    ("la diapositiva 18 (alertas en Postgres)", 42368, 96, 42363, 16, 42363, 6),
]
CONTROL_HORA, CONTROL_DIA = "73.85", "74.02"   # CC-004: hora 13:00 y promedio del día


def consultar():
    """Los ocho valores de CONSULTA, o un texto con el problema."""
    try:
        r = subprocess.run(["docker", "exec", "pmd-postgis", "psql", "-U", "postgres", "-tAc", CONSULTA],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "pmd-postgis no responde: ¿está Docker abierto? docker compose up -d --wait"
    if r.returncode != 0:
        if "No such container" in r.stderr or "is not running" in r.stderr:
            return "pmd-postgis no está corriendo: docker compose up -d --wait"
        if "does not exist" in r.stderr:
            return ("faltan tablas: Postgres partió con un volumen viejo. "
                    "docker compose down -v y docker compose up -d --wait")
        return f"psql falló: {r.stderr.strip()}"
    return r.stdout.strip().split("|")


def principal():
    v = consultar()
    if isinstance(v, str):
        print(f"✗ {v}")
        return False
    ev, rh, rh_n, rd, rd_n, al = (int(x) for x in v[:6])
    cc_hora, cc_dia = v[6] or None, v[7] or None

    print(f"eventos          {ev:>7,}".replace(",", "."))
    print(f"resumen_horario  {rh:>7} filas · sum(n) = {rh_n:,}".replace(",", "."))
    print(f"resumen_diario   {rd:>7} filas · sum(n) = {rd_n:,}".replace(",", "."))
    print(f"alertas          {al:>7} filas")
    print(f"control CC-004   hora 13:00 = {cc_hora or '—'} · día = {cc_dia or '—'}")

    control_ok = cc_hora in (None, CONTROL_HORA) and cc_dia in (None, CONTROL_DIA)
    for nombre, *esperado in ESTADOS:
        if (ev, rh, rh_n, rd, rd_n, al) == tuple(esperado) and control_ok:
            print(f"\n✓ Calza con: {'' if nombre.startswith('el ') else 'después de '}{nombre}")
            if rd == 16 and al == 0:
                print("  (Si ya publicaron alerta_aire_postgres e hicieron Clear de avisar, alertas debería ser 6: "
                      "abran Executions en n8n y miren el nodo en rojo; ¿publicaron de nuevo?)")
            return True

    print("\n✗ No calza con ningún paso de la receta. Pistas:")
    if ev > 42368:
        print("  · eventos > 42.368: no deduplicó. Revisen la clave primaria de eventos en sql/01_tablas.sql.")
    if ev == 42368 and rh < 96 and (rh, rh_n) != (80, 35298):
        print("  · Alguna ejecución sigue roja: miren la vista Grid de eventos_por_hora.")
    if rh_n > ev:
        print("  · sum(n) de resumen_horario > eventos: resumir está sumando en vez de reemplazar. Revisen el DO UPDATE.")
    if rd_n == 42344:
        print("  · resumen_diario con 42.344: encendieron el DAG nocturno antes del Clear de las seis (diap. 13). "
              "Clear de resumen_diario y queda bien.")
    if al > 6:
        print("  · alertas > 6: el nodo Postgres está insertando sin match (o con match por una sola columna).")
    if 0 < al < 6:
        print("  · alertas entre 1 y 5: falta hacer Clear de avisar en todas las ejecuciones (las seis).")
    if not control_ok:
        print(f"  · Control: CC-004 tendría que dar {CONTROL_HORA} a las 13:00 y {CONTROL_DIA} en el día.")
    if ev and ev not in (35294, 42368):
        print("  · Si el DAG está corriendo, esperen a que terminen las ejecuciones y vuelvan a correrlo.")
    return False


if __name__ == "__main__":
    sys.exit(0 if principal() else 1)
