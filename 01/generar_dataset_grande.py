#!/usr/bin/env python3
"""
Genera demo_grande.csv para la demo comparativa de la Clase 1.

Mismo esquema que demo_chico.csv, pero con millones de filas.
Ejecutar ANTES de la clase (demora unos minutos y ocupa ~700 MB con 10M filas):

    python3 generar_dataset_grande.py            # 10.000.000 filas (default)
    python3 generar_dataset_grande.py 2000000    # versión más liviana si el disco anda justo
"""
import csv, random, sys, datetime, os

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_grande.csv")

random.seed(102)
ZONAS = ["Placeres", "Almendral", "Puerto", "Playa Ancha", "Cerro Alegre",
         "Rodelillo", "Barón", "Recreo", "Miraflores", "Achupallas"]
base = datetime.datetime(2026, 7, 1, 6, 0, 0)

with open(SALIDA, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id_viaje", "zona_origen", "zona_destino", "inicio", "duracion_min", "distancia_km"])
    for i in range(1, N + 1):
        zo, zd = random.choice(ZONAS), random.choice(ZONAS)
        t = base + datetime.timedelta(seconds=random.randint(0, 30 * 24 * 3600))
        dur = round(random.lognormvariate(2.9, 0.5), 1)
        dist = round(dur * random.uniform(0.25, 0.6), 2)
        w.writerow([i, zo, zd, t.isoformat(), dur, dist])
        if i % 1_000_000 == 0:
            print(f"  {i:,} filas...")

print(f"Listo: {SALIDA} ({os.path.getsize(SALIDA) / 1e6:.0f} MB, {N:,} filas)")
