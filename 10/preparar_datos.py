"""Laboratorio 10 — los seis archivos que van a «llegar» a NiFi, y el driver JDBC de Postgres.

    python3 preparar_datos.py

Escribe pendientes/eventos_0800.csv … eventos_1300.csv (7.200 eventos cada uno, una hora
de los 16 sensores del Lab 06, en orden de llegada) y baja el JAR de PostgreSQL JDBC a
drivers/. Sin paquetes de Python: solo la biblioteca estándar y ../06/generador.py.
Se puede correr las veces que quieran: los CSV salen idénticos y el JAR no se vuelve a bajar.
"""
import hashlib, itertools, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "06"))
from generador import ESTACIONES, eventos  # noqa: E402  (el mismo generador del Lab 06, sin copiarlo)

T0 = datetime(2026, 11, 13, 8, 0, tzinfo=timezone(timedelta(hours=-3)))  # vie 13-nov, el día del lab
POR_HORA = 7200                                                          # un evento cada 0,5 s
HORAS = ["0800", "0900", "1000", "1100", "1200", "1300"]
JDBC = "42.7.14"                       # última 42.7.x en Maven Central al armar el lab (11-nov-2026)
MAVEN = f"https://repo1.maven.org/maven2/org/postgresql/postgresql/{JDBC}/postgresql-{JDBC}.jar"

# Lo que tiene que salir (guía docente, sección 2): archivo → (repetidas, únicas, filas calidad_aire > 70)
ESPERADO = {"0800": (137, 7063, 607), "0900": (163, 7037, 570), "1000": (138, 7062, 644),
            "1100": (126, 7074, 544), "1200": (126, 7074, 624), "1300": (142, 7058, 561)}


def escribir_csv():
    pendientes = AQUI / "pendientes"
    pendientes.mkdir(exist_ok=True)
    gen = eventos(T0)
    claves_vistas, problemas = set(), []
    for hora in HORAS:
        bloque = list(itertools.islice(gen, POR_HORA))  # en el orden en que salen: los tardíos quedan donde llegaron
        filas = [(e["estacion_id"], e["tipo_sensor"], f"{e['valor']:.1f}", e["timestamp"]) for e in bloque]
        ruta = pendientes / f"eventos_{hora}.csv"
        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            f.write("estacion_id,tipo_sensor,valor,ts\n")
            f.writelines(",".join(fila) + "\n" for fila in filas)

        # verificación del archivo
        por_clave = {}
        for fila in filas:
            if por_clave.setdefault((fila[0], fila[3]), fila) != fila:
                problemas.append(f"{ruta.name}: la clave {fila[0]} {fila[3]} aparece con valores distintos")
        unicas = len(por_clave)
        altos = sum(1 for f in filas if f[1] == "calidad_aire" and float(f[2]) > 70)  # con repetidas: el record.count de «alertas»
        obtenido = (len(filas) - unicas, unicas, altos)
        if obtenido != ESPERADO[hora]:
            problemas.append(f"{ruta.name}: repetidas/únicas/aire>70 = {obtenido}, esperado {ESPERADO[hora]}")
        if claves_vistas & por_clave.keys():
            problemas.append(f"{ruta.name}: repite claves de un archivo anterior")
        claves_vistas |= por_clave.keys()
        if set(Counter(f[0] for f in filas)) != {e for e, _ in ESTACIONES}:
            problemas.append(f"{ruta.name}: no aparecen las 16 estaciones")
        if any("." not in f[2] for f in filas):
            problemas.append(f"{ruta.name}: hay valores sin decimal")
    return len(claves_vistas), problemas


def bajar_jar():
    drivers = AQUI / "drivers"
    drivers.mkdir(exist_ok=True)
    jar = drivers / f"postgresql-{JDBC}.jar"
    if jar.exists():
        print(f"Driver JDBC: ya está {jar.relative_to(AQUI)}")
        return
    try:
        datos = urllib.request.urlopen(MAVEN, timeout=60).read()
        sha1 = urllib.request.urlopen(MAVEN + ".sha1", timeout=30).read().decode().split()[0]
    except OSError as e:
        print(f"⚠️  No se pudo bajar el driver JDBC ({e}).\n"
              f"    Copien postgresql-{JDBC}.jar del pendrive a drivers/. Los CSV no dependen de él.")
        return
    if hashlib.sha1(datos).hexdigest() != sha1:
        sys.exit(f"El JAR bajado no calza con su SHA-1 de Maven ({sha1}). Vuelvan a correr el script.")
    jar.write_bytes(datos)
    print(f"Driver JDBC: {jar.relative_to(AQUI)} ({len(datos) // 1024} KB, SHA-1 OK)")


if __name__ == "__main__":
    unicas, problemas = escribir_csv()
    if unicas != 42368:
        problemas.append(f"claves únicas en total = {unicas}, esperado 42368")
    if problemas:
        sys.exit("Verificación FALLÓ:\n  " + "\n  ".join(problemas))
    bajar_jar()
    print(f"Verificación OK: {len(HORAS)} archivos · {len(HORAS) * POR_HORA:,} filas · "
          f"{unicas:,} claves únicas → pendientes/".replace(",", "."))
