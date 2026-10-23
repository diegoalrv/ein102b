# Laboratorios — Procesamiento Masivo de Datos

**ELE051-B / EIN102B** · USM 2026-2 · Paralelo 701

Código e instrucciones de los laboratorios del curso. Un directorio por laboratorio.

| Lab | Clase | Tema |
|---|---|---|
| [`01/`](01/) | Vie 07-ago-2026 | Fuentes de datos masivos: escala, geoespacial, streams y grafos |
| [`02/`](02/) | Vie 14-ago-2026 | Docker en serio (puertos, volúmenes) y primeros pasos con PostGIS |
| [`03/`](03/) | Vie 21-ago-2026 | Representación de datos geoespaciales: formatos, SRID y datos reales de datos.gob.cl |
| [`04/`](04/) | Vie 28-ago-2026 | Lenguajes de consulta geoespaciales: predicados, índices GIST y el filtro en dos fases |
| [`05/`](05/) | Vie 04-sep-2026 | PostGIS de punta a punta: `docker compose`, OpenStreetMap con `ogr2ogr`, capas derivadas, consultas y salida — cierre del bloque geoespacial |
| [`06/`](06/) | Vie 25-sep y 02-oct-2026 | Redis: estructuras en memoria, Pub/Sub y Streams con consumer groups, contra un stream compartido en vivo |
| [`07/`](07/) | Vie 09-oct-2026 | HBase: modelo de datos, la row key como índice, *hotspotting* y el camino de escritura (LSM) en disco |
| [`08/`](08/) | Vie 23-oct-2026 | Neo4j I: el grafo de propiedades y Cypher — patrones de uno y varios saltos, CREATE/MERGE — sobre una red de paradas del Gran Concepción |
| [`09/`](09/) | Vie 30-oct-2026 | Neo4j II: shortestPath y caminos ponderados con reduce, agregaciones y NOT EXISTS, PROFILE e índices, carga idempotente con LOAD CSV + MERGE |

## Empezar

```bash
git clone https://github.com/diegoalrv/ein102b.git && cd ein102b/01 && python3 generar_muestras.py
```

Los datos no están versionados: el `.gitignore` excluye `*.csv`, `*.ndjson` y `*.geojson`, y cada laboratorio trae su propio generador con semilla fija. El generador verifica lo que produce y falla ruidosamente si algo no cuadra, así que si termina sin la línea `Verificación OK`, no sigas. Las instrucciones completas están en el README de cada laboratorio. (El Lab 02 no tiene datos propios: reutiliza la muestra A del Lab 01. El Lab 03 tampoco genera nada: usa datos públicos reales de datos.gob.cl, que se descargan una vez y se preparan con `preparar_datos.py`. El Lab 04 genera sus 500.000 puntos dentro de PostgreSQL y reutiliza el escenario de los Labs 01 y 03. El Lab 05 usa el extracto de Chile de OpenStreetMap, que se descarga una vez de Geofabrik y se recorta con su propio `preparar_datos.py`; además reutiliza los Labs 01 y 03.)

## Requisitos

- Python 3.11+ con `pandas`, `matplotlib` y `jupyter`
- Docker (se usa durante todo el semestre — conviene verificar `docker run hello-world` antes de la primera sesión)
- Desde el Lab 02: `sqlalchemy` y `psycopg2-binary` (`pip install sqlalchemy psycopg2-binary`)
- Desde el Lab 03: la imagen `postgis/postgis:16-3.4-alpine` (~90 MB) — `preparar_datos.py` corre desde ahí el cargador de shapefiles `shp2pgsql`, que la imagen del lab no trae
- Desde el Lab 05: `docker compose` (viene con Docker Desktop) y la imagen `pmd-postgis-gdal`, que se construye una vez con `docker compose build` en `05/` (PostgreSQL 16 sobre Debian bookworm con PostGIS y `gdal-bin`, en el puerto 5434; necesita red esa única vez)
- Lab 06: `redis`, `pandas` y `pyarrow` (`pip install -r 06/requirements.txt`)
- Lab 07: `happybase` (`pip install -r 07/requirements.txt`) y la imagen `pmd-hbase`, que se construye una vez con `docker compose build` en `07/` (HBase 2.5.15 standalone; descarga ~340 MB y pide ~4 GB de RAM para Docker)
- Lab 08: el driver `neo4j` (`pip install -r 08/requirements.txt`) y la imagen `neo4j:5-community` (~350 MB de descarga, ~1 GB en disco; `docker pull neo4j:5-community` antes de abrir el notebook)
- Lab 09: lo mismo que el Lab 08 (`pip install -r 09/requirements.txt` y la imagen `neo4j:5-community`)

## Versión docente

Los notebooks `*_docente.ipynb` — con las soluciones y las respuestas esperadas de la cátedra — no se versionan: el `.gitignore` los excluye. Este repositorio trae solo el material del laboratorio.
