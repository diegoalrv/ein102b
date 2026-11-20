"""Laboratorio 11 — los mismos seis CSV de la C14, en data/, para que Airflow los lea.

    python3 preparar_datos.py

Copia ../10/pendientes/eventos_0800.csv … eventos_1300.csv a data/ y los verifica byte a byte
(SHA-256). Si no están en ../10/pendientes/, primero corre ../10/preparar_datos.py, que los
genera con ../06/generador.py: hay un solo generador, así que los bytes son siempre los mismos.
Sin paquetes de Python: solo la biblioteca estándar.
Se puede correr las veces que quieran: los archivos de data/ quedan idénticos.
"""
import csv, hashlib, shutil, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).parent
LAB10 = AQUI.parent / "10"
ORIGEN, DESTINO = LAB10 / "pendientes", AQUI / "data"
CABECERA = ["estacion_id", "tipo_sensor", "valor", "ts"]
POR_HORA = 7200

# Lo que tiene que salir (guía docente, sección 2): archivo → (únicas, SHA-256)
ESPERADO = {
    "0800": (7063, "fa0759f099fe7aefdfb40587f03410d31cc7b5bcc522335b8fb6056674a2d62a"),
    "0900": (7037, "00c0d334f3ae0d484e072c0c7c3072a180aabc16434338ea1235312aa767a1a7"),
    "1000": (7062, "fa20d8a9f1eea53435367e1ee96d7d1cdc69b7ea20cc90469fe5b1afb359a6db"),
    "1100": (7074, "ceeb97347aa01e2881ee1796829f308862e06ae6f0674519052a56d6e8199e1b"),
    "1200": (7074, "01dae2b836ca5ab01598caec52c3e8fd7fcc37e94bde99c45e170367a1ea75bc"),
    "1300": (7058, "5d87b6e44419ab30dc635e3792956320001a004b67729f73c83cc177ac5f8a1a"),
}


def asegurar_origen():
    """Si faltan CSV en ../10/pendientes/, los genera el preparar_datos.py del Lab 10."""
    if all((ORIGEN / f"eventos_{h}.csv").exists() for h in ESPERADO):
        return
    print("Faltan CSV en ../10/pendientes/: los genero con ../10/preparar_datos.py …")
    r = subprocess.run([sys.executable, "preparar_datos.py"], cwd=LAB10, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit(f"../10/preparar_datos.py falló:\n{r.stdout}{r.stderr}")


def verificar():
    claves, problemas = set(), []
    for hora, (e_unicas, e_sha) in ESPERADO.items():
        ruta = DESTINO / f"eventos_{hora}.csv"
        if hashlib.sha256(ruta.read_bytes()).hexdigest() != e_sha:
            problemas.append(f"{ruta.name}: el SHA-256 no calza (¿cambió el generador del Lab 06?)")
        with open(ruta, encoding="utf-8", newline="") as f:
            lector = csv.reader(f)
            if next(lector) != CABECERA:
                problemas.append(f"{ruta.name}: la cabecera no es {','.join(CABECERA)}")
            filas = list(lector)
        propias = {(r[0], r[3]) for r in filas}
        if (len(filas), len(propias)) != (POR_HORA, e_unicas):
            problemas.append(f"{ruta.name}: filas/únicas = {len(filas)}/{len(propias)}, esperado {POR_HORA}/{e_unicas}")
        claves |= propias
    if len(claves) != 42368:
        problemas.append(f"claves únicas en total = {len(claves)}, esperado 42368")
    return len(claves), problemas


if __name__ == "__main__":
    asegurar_origen()
    DESTINO.mkdir(exist_ok=True)
    for hora in ESPERADO:
        shutil.copy2(ORIGEN / f"eventos_{hora}.csv", DESTINO)
    unicas, problemas = verificar()
    if problemas:
        sys.exit("Verificación FALLÓ:\n  " + "\n  ".join(problemas))
    print(f"Verificación OK: {len(ESPERADO)} archivos · {len(ESPERADO) * POR_HORA:,} filas · "
          f"{unicas:,} claves únicas → data/".replace(",", "."))
