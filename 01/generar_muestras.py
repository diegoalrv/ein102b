#!/usr/bin/env python3
"""
Reconstruye los archivos de datos del Laboratorio 01, que no se versionan.

    python3 generar_muestras.py             # genera lo que falte
    python3 generar_muestras.py --forzar    # regenera todo, sobrescribiendo

Produce demo_chico.csv, muestra_A.geojson, muestra_B.ndjson, muestra_C_nodos.csv
y muestra_C_aristas.csv. (demo_grande.csv NO: ese lo genera el notebook con
generar_dataset_grande.py.)

Las muestras A y C son fixtures fijas: van escritas como literales, porque el
laboratorio depende de su estructura exacta (la zona de restricción tiene que
contener ciertas estaciones; el grafo tiene que tener a "Rutas Inteligentes"
como proyecto más conectado). La muestra B y demo_chico.csv se generan con
semilla fija, con los conteos de imperfecciones forzados por construcción —
no dejados al azar, porque el notebook docente los documenta.
"""
import csv, json, os, random, sys

from generar_dataset_grande import generar_viajes

AQUI = os.path.dirname(os.path.abspath(__file__))
FORZAR = "--forzar" in sys.argv


def ruta(nombre):
    return os.path.join(AQUI, nombre)


def toca(nombre):
    """False si el archivo ya existe y no se pidió --forzar."""
    if os.path.exists(ruta(nombre)) and not FORZAR:
        print(f"  {nombre} ya existe, se conserva (usa --forzar para regenerar)")
        return False
    return True


# ---------------------------------------------------------------- Muestra A
# id, nombre, comuna, variable, activa, (lon, lat)
ESTACIONES = [
    ("EST-001", "Estación Costanera",       "Viña del Mar",  "temperatura", True,  (-71.46561, -33.00863)),
    ("EST-002", "Estación Cerro Cárcel",    "Concón",        "PM2.5",       True,  (-71.52683, -33.03743)),
    ("EST-003", "Estación Av. Argentina",   "Viña del Mar",  "PM2.5",       True,  (-71.55681, -33.08105)),
    ("EST-004", "Estación Muelle Prat",     "Quilpué",       "temperatura", True,  (-71.58564, -33.08821)),
    ("EST-005", "Estación Portales",        "Concón",        "PM10",        True,  (-71.45802, -33.05483)),
    ("EST-006", "Estación Sausalito",       "Valparaíso",    "PM10",        True,  (-71.52302, -33.09225)),
    ("EST-007", "Estación Reñaca",          "Villa Alemana", "temperatura", True,  (-71.42010, -32.97189)),
    ("EST-008", "Estación Curauma",         "Viña del Mar",  "PM2.5",       True,  (-71.58788, -33.00971)),
    ("EST-009", "Estación Quilpué Centro",  "Concón",        "ruido",       False, (-71.38595, -32.98825)),
    ("EST-010", "Estación Belloto",         "Viña del Mar",  "PM2.5",       True,  (-71.35692, -33.01532)),
    ("EST-011", "Estación Con Con",         "Concón",        "PM10",        True,  (-71.40528, -32.99334)),
    ("EST-012", "Estación Laguna Verde",    "Valparaíso",    "PM2.5",       True,  (-71.39516, -33.01174)),
    ("EST-013", "Estación Placilla",        "Villa Alemana", "temperatura", True,  (-71.44892, -33.05490)),
    ("EST-014", "Estación Miraflores Alto", "Viña del Mar",  "temperatura", True,  (-71.60977, -33.00630)),
    ("EST-015", "Estación Forestal",        "Quilpué",       "PM2.5",       True,  (-71.55005, -32.97323)),
    ("EST-016", "Estación Achupallas",      "Villa Alemana", "ruido",       True,  (-71.34553, -33.08888)),
    ("EST-017", "Estación Rodelillo",       "Viña del Mar",  "temperatura", True,  (-71.57109, -32.97154)),
    ("EST-018", "Estación El Salto",        "Villa Alemana", "PM2.5",       True,  (-71.52489, -32.98224)),
    ("EST-019", "Estación Villa Alemana",   "Viña del Mar",  "temperatura", True,  (-71.50636, -32.99792)),
    ("EST-020", "Estación Peñablanca",      "Quilpué",       "PM10",        True,  (-71.45743, -33.08451)),
]

ZONA = [[[-71.635, -33.045], [-71.615, -33.045], [-71.615, -33.030],
         [-71.635, -33.030], [-71.635, -33.045]]]

RUTA_METRO = [[-71.628, -33.041], [-71.601, -33.036], [-71.575, -33.024], [-71.552, -33.010]]


def muestra_A():
    features = [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": list(coord)},
         "properties": {"id": eid, "nombre": nombre, "comuna": comuna,
                        "variable": variable, "activa": activa}}
        for eid, nombre, comuna, variable, activa, coord in ESTACIONES
    ]
    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": ZONA},
        "properties": {"id": "ZON-001", "nombre": "Zona de restricción portuaria", "tipo": "zona"}})
    features.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": RUTA_METRO},
        "properties": {"id": "RUT-014", "nombre": "Ruta troncal metro Valparaíso", "tipo": "ruta"}})

    with open(ruta("muestra_A.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, indent=1, ensure_ascii=False)
    return features


# ---------------------------------------------------------------- Muestra B
EVENTOS_POR_ESTACION = {
    "EST-001": 36, "EST-002": 37, "EST-003": 47, "EST-004": 43,
    "EST-005": 27, "EST-006": 36, "EST-007": 29, "EST-008": 45,
}
SIN_PM25 = 19    # el sensor no reportó la lectura
CON_ERROR = 12   # reportó -999.0, el código de error del fabricante
CON_BATERIA = 12  # solo algunos modelos envían este campo


def muestra_B():
    rng = random.Random(7)

    eventos = []
    for estacion, n in EVENTOS_POR_ESTACION.items():
        for _ in range(n):
            seg = rng.randint(0, 24 * 3600 - 1)
            eventos.append({
                "estacion": estacion,
                "ts": f"2026-08-03T{seg // 3600:02d}:{seg % 3600 // 60:02d}:{seg % 60:02d}Z",
                "pm25": min(119.3, max(5.5, round(rng.lognormvariate(3.2, 0.6), 1))),
                "temp_c": round(rng.uniform(6.0, 22.0), 1),
            })

    # Las imperfecciones se reparten por construcción, no por probabilidad:
    # los conteos exactos están documentados en el notebook docente.
    idx = list(range(len(eventos)))
    rng.shuffle(idx)
    for i in idx[:SIN_PM25]:
        del eventos[i]["pm25"]
    for i in idx[SIN_PM25:SIN_PM25 + CON_ERROR]:
        eventos[i]["pm25"] = -999.0
    for i in rng.sample(idx, CON_BATERIA):
        eventos[i]["bateria_pct"] = rng.randint(5, 98)

    # Desordenados en el tiempo: así llegan los eventos de un stream real.
    rng.shuffle(eventos)
    assert [e["ts"] for e in eventos] != sorted(e["ts"] for e in eventos), \
        "la muestra B debe quedar desordenada en el tiempo"

    with open(ruta("muestra_B.ndjson"), "w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return eventos


# ---------------------------------------------------------------- Muestra C
NODOS = [
    ("N01", "Antonia Rojas", "Persona"), ("N02", "Benjamín Soto", "Persona"),
    ("N03", "Camila Fuentes", "Persona"), ("N04", "Diego Herrera", "Persona"),
    ("N05", "Emilia Castro", "Persona"), ("N06", "Felipe Núñez", "Persona"),
    ("N07", "Gabriela Pinto", "Persona"), ("N08", "Hernán Vidal", "Persona"),
    ("N09", "USM", "Organización"), ("N10", "Puerto Valparaíso", "Organización"),
    ("N11", "MetroVal", "Organización"), ("N12", "SercoTec V Región", "Organización"),
    ("N13", "Monitoreo Aire GV", "Proyecto"), ("N14", "Rutas Inteligentes", "Proyecto"),
    ("N15", "Censo Digital 2026", "Proyecto"),
]

ARISTAS = [
    ("N01", "N09", "TRABAJA_EN", 2021), ("N01", "N13", "PARTICIPA_EN", 2024),
    ("N01", "N15", "PARTICIPA_EN", 2024), ("N02", "N10", "TRABAJA_EN", 2022),
    ("N02", "N14", "PARTICIPA_EN", 2024), ("N03", "N11", "TRABAJA_EN", 2023),
    ("N03", "N14", "PARTICIPA_EN", 2025), ("N03", "N15", "PARTICIPA_EN", 2025),
    ("N04", "N09", "TRABAJA_EN", 2024), ("N04", "N14", "PARTICIPA_EN", 2025),
    ("N04", "N13", "PARTICIPA_EN", 2026), ("N05", "N09", "TRABAJA_EN", 2020),
    ("N05", "N14", "PARTICIPA_EN", 2024), ("N06", "N09", "TRABAJA_EN", 2021),
    ("N06", "N14", "PARTICIPA_EN", 2024), ("N07", "N12", "TRABAJA_EN", 2022),
    ("N07", "N15", "PARTICIPA_EN", 2026), ("N07", "N13", "PARTICIPA_EN", 2024),
    ("N08", "N09", "TRABAJA_EN", 2023), ("N08", "N15", "PARTICIPA_EN", 2024),
    ("N08", "N13", "PARTICIPA_EN", 2025), ("N01", "N02", "COLABORA_CON", 2023),
    ("N01", "N07", "COLABORA_CON", 2024), ("N02", "N07", "COLABORA_CON", 2023),
    ("N03", "N04", "COLABORA_CON", 2024), ("N03", "N06", "COLABORA_CON", 2023),
    ("N07", "N08", "COLABORA_CON", 2026), ("N10", "N13", "FINANCIA", 2026),
    ("N12", "N14", "FINANCIA", 2026), ("N12", "N15", "FINANCIA", 2025),
]


def muestra_C():
    with open(ruta("muestra_C_nodos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "etiqueta", "tipo"])
        w.writerows(NODOS)
    with open(ruta("muestra_C_aristas.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origen", "destino", "relacion", "desde"])
        w.writerows(ARISTAS)


# ---------------------------------------------------------------- verificación
def verificar():
    """Comprueba lo que el notebook docente promete sobre cada muestra."""
    gj = json.load(open(ruta("muestra_A.geojson"), encoding="utf-8"))
    geoms = [ft["geometry"]["type"] for ft in gj["features"]]
    assert len(gj["features"]) == 22, len(gj["features"])
    assert geoms.count("Point") == 20 and geoms.count("Polygon") == 1 and geoms.count("LineString") == 1
    # el Ejercicio 2.2 usa properties["nombre"] como etiqueta del gráfico
    assert all("nombre" in ft["properties"] for ft in gj["features"])

    eventos = [json.loads(l) for l in open(ruta("muestra_B.ndjson"), encoding="utf-8")]
    ts = [e["ts"] for e in eventos]
    assert len(eventos) == 300, len(eventos)
    assert len({e["estacion"] for e in eventos}) == 8
    assert ts != sorted(ts), "debe estar desordenado en el tiempo"
    assert sum("pm25" not in e for e in eventos) == SIN_PM25
    assert sum(e.get("pm25") == -999.0 for e in eventos) == CON_ERROR
    assert sum("bateria_pct" in e for e in eventos) == CON_BATERIA

    nodos = list(csv.DictReader(open(ruta("muestra_C_nodos.csv"), encoding="utf-8")))
    aristas = list(csv.DictReader(open(ruta("muestra_C_aristas.csv"), encoding="utf-8")))
    assert len(nodos) == 15 and len(aristas) == 30
    tipos = [n["tipo"] for n in nodos]
    assert tipos.count("Persona") == 8 and tipos.count("Organización") == 4 and tipos.count("Proyecto") == 3
    grado = {}
    for a in aristas:
        for extremo in (a["origen"], a["destino"]):
            grado[extremo] = grado.get(extremo, 0) + 1
    # todos los nodos participan en alguna arista: si no, el join del 2.6 deja NaN
    assert len(grado) == 15, set(n["id"] for n in nodos) - set(grado)
    proyectos = {n["id"]: n["etiqueta"] for n in nodos if n["tipo"] == "Proyecto"}
    top_proyecto = max(proyectos, key=lambda p: grado[p])
    assert top_proyecto == "N14", top_proyecto  # "Rutas Inteligentes", el que espera el 2.6

    viajes = list(csv.DictReader(open(ruta("demo_chico.csv"), encoding="utf-8")))
    assert len(viajes) == 1000, len(viajes)
    assert len({v["zona_origen"] for v in viajes}) == 10

    print("Verificación OK: 22 features · 300 eventos "
          f"({SIN_PM25} sin pm25, {CON_ERROR} con -999, {CON_BATERIA} con batería) · "
          "15 nodos y 30 aristas · 1.000 viajes")


if __name__ == "__main__":
    print("Generando muestras del Laboratorio 01...")
    if toca("muestra_A.geojson"):
        muestra_A()
    if toca("muestra_B.ndjson"):
        muestra_B()
    if toca("muestra_C_nodos.csv"):  # los dos archivos de C se escriben siempre juntos
        muestra_C()
    if toca("demo_chico.csv"):
        generar_viajes(1000, ruta("demo_chico.csv"), seed=1)
    verificar()
