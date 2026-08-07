#!/usr/bin/env python3
"""
Demo comparativa de la Clase 1: la MISMA consulta sobre un dataset chico y uno grande.

Consulta: promedio de duración de viaje agrupado por zona de origen.

Uso en clase (proyectado):
    python3 demo_comparativa.py demo_chico.csv
    python3 demo_comparativa.py demo_grande.csv

Imprime tiempo de carga, tiempo de consulta y memoria pico del proceso,
para completar la tabla de la diapositiva 10.
"""
import sys, time, os, resource
import pandas as pd

archivo = sys.argv[1] if len(sys.argv) > 1 else "demo_chico.csv"
mb = os.path.getsize(archivo) / 1e6
print(f"\n=== {archivo} ({mb:.1f} MB en disco) ===")

def memoria_pico_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3  # macOS: bytes, Linux: KB

# 1) Carga completa en memoria (el enfoque "ingenuo")
t0 = time.perf_counter()
df = pd.read_csv(archivo)
t_carga = time.perf_counter() - t0
print(f"Carga:    {t_carga:8.2f} s   ({len(df):,} filas)")

# 2) La consulta: promedio de duración por zona de origen
t0 = time.perf_counter()
resultado = df.groupby("zona_origen")["duracion_min"].mean().sort_values(ascending=False)
t_consulta = time.perf_counter() - t0
print(f"Consulta: {t_consulta:8.2f} s")
print(f"Memoria pico del proceso: {memoria_pico_mb():,.0f} MB")

print("\nTop 3 zonas por duración promedio:")
print(resultado.head(3).round(1).to_string())

# Pregunta para la sala: ¿y si el archivo tuviera 100M de filas? ¿1.000M?
# ¿Sirve comprar más RAM para siempre... o el problema es el enfoque?
