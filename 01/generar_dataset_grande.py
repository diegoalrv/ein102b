#!/usr/bin/env python3
"""
Genera demo_grande.csv para la demo comparativa de la Clase 1.

Mismo esquema que demo_chico.csv, pero con millones de filas.
Ejecutar ANTES de la clase (demora unos minutos y ocupa ~600 MB con 10M filas):

    python3 generar_dataset_grande.py            # 10.000.000 filas (default)
    python3 generar_dataset_grande.py 2000000    # lo que corren los equipos en el laboratorio

`generar_muestras.py` importa `generar_viajes()` para producir demo_chico.csv
con el mismo esquema.
"""
import csv, random, sys, datetime, os

AQUI = os.path.dirname(os.path.abspath(__file__))

ZONAS = ["Placeres", "Almendral", "Puerto", "Playa Ancha", "Cerro Alegre",
         "Rodelillo", "Barón", "Recreo", "Miraflores", "Achupallas"]


def generar_viajes(n, salida, seed=102, progreso=False):
    """Escribe `n` viajes simulados del Gran Valparaíso en `salida` (CSV)."""
    rng = random.Random(seed)
    base = datetime.datetime(2026, 7, 1, 6, 0, 0)

    with open(salida, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_viaje", "zona_origen", "zona_destino", "inicio", "duracion_min", "distancia_km"])
        for i in range(1, n + 1):
            zo, zd = rng.choice(ZONAS), rng.choice(ZONAS)
            t = base + datetime.timedelta(seconds=rng.randint(0, 30 * 24 * 3600))
            dur = round(rng.lognormvariate(2.9, 0.5), 1)
            dist = round(dur * rng.uniform(0.25, 0.6), 2)
            w.writerow([i, zo, zd, t.isoformat(), dur, dist])
            if progreso and i % 1_000_000 == 0:
                print(f"  {i:,} filas...")
    return salida


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
    SALIDA = os.path.join(AQUI, "demo_grande.csv")
    generar_viajes(N, SALIDA, progreso=True)
    print(f"Listo: {SALIDA} ({os.path.getsize(SALIDA) / 1e6:.0f} MB, {N:,} filas)")
