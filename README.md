# Laboratorios — Procesamiento Masivo de Datos

**ELE051-B / EIN102B** · USM 2026-2 · Paralelo 701

Código e instrucciones de los laboratorios del curso. Un directorio por laboratorio.

| Lab | Clase | Tema |
|---|---|---|
| [`01/`](01/) | Vie 07-ago-2026 | Fuentes de datos masivos: escala, geoespacial, streams y grafos |
| [`02/`](02/) | Vie 14-ago-2026 | Docker en serio (puertos, volúmenes) y primeros pasos con PostGIS |
| [`03/`](03/) | Vie 21-ago-2026 | Representación de datos geoespaciales: formatos, SRID y datos reales de datos.gob.cl |
| [`04/`](04/) | Vie 28-ago-2026 | Lenguajes de consulta geoespaciales: predicados, índices GIST y el filtro en dos fases |

## Empezar

```bash
git clone https://github.com/diegoalrv/ein102b.git && cd ein102b/01 && python3 generar_muestras.py
```

Los datos no están versionados: el `.gitignore` excluye `*.csv`, `*.ndjson` y `*.geojson`, y cada laboratorio trae su propio generador con semilla fija. El generador verifica lo que produce y falla ruidosamente si algo no cuadra, así que si termina sin la línea `Verificación OK`, no sigas. Las instrucciones completas están en el README de cada laboratorio. (El Lab 02 no tiene datos propios: reutiliza la muestra A del Lab 01. El Lab 03 tampoco genera nada: usa datos públicos reales de datos.gob.cl, que se descargan una vez y se preparan con `preparar_datos.py`. El Lab 04 genera sus 500.000 puntos dentro de PostgreSQL y reutiliza el escenario de los Labs 01 y 03.)

## Requisitos

- Python 3.11+ con `pandas`, `matplotlib` y `jupyter`
- Docker (se usa durante todo el semestre — conviene verificar `docker run hello-world` antes de la primera sesión)
- Desde el Lab 02: `sqlalchemy` y `psycopg2-binary` (`pip install sqlalchemy psycopg2-binary`)
- Desde el Lab 03: la imagen `postgis/postgis:16-3.4-alpine` (~90 MB) — `preparar_datos.py` corre desde ahí el cargador de shapefiles `shp2pgsql`, que la imagen del lab no trae

## Versión docente

Los notebooks `*_docente.ipynb` — con las soluciones y las respuestas esperadas de la cátedra — no se versionan: el `.gitignore` los excluye. Este repositorio trae solo el material del laboratorio.
