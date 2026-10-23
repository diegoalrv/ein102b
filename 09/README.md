# Laboratorio 09 — Clase 12 (Vie 30-oct): Neo4j II, caminos, agregaciones y carga masiva (para trabajar en casa)

> En la Clase 12 vimos primero la teoría y después estos ejercicios en vivo. Este laboratorio lo hacen en casa, a su ritmo; no se entrega ni se evalúa. Parte del mismo grafo del Lab 08, así que conviene haberlo hecho antes. Cuenten con 1,5–2 horas.

*Libreto: `Clases/Clase 12 (3010)/Clase 12 (3010) — Libreto.md` · guía docente: `Clases/Clase 12 (3010)/Clase 12 (3010) — Laboratorio 09.md` (en la carpeta del curso, fuera de este repositorio).*

Segunda sesión del bloque de grafos. En el Lab 08 preguntábamos «¿a qué paradas llego?»; hoy, **cuál es la mejor ruta** (¿menos paradas o menos minutos?), qué **no** se alcanza, cómo decide Neo4j por dónde buscar (`PROFILE` e índices) y cómo se carga un archivo **sin duplicar nada** si se carga dos veces (`LOAD CSV` + `MERGE`). Al final, una línea exprés nueva cambia la mejor ruta sin tocar ninguna consulta.

## Qué se necesita

Lo mismo que el Lab 08. Si ya lo hicieron, la imagen y el `.venv` ya están.

- **Docker** con `docker compose` y ~1,5 GB de RAM libre.
- La imagen `neo4j:5-community`, descargada una vez, antes de abrir el notebook:

  ```bash
  docker pull neo4j:5-community    # ~350 MB de descarga, ~1 GB en disco
  ```

- Python con el driver `neo4j`, `pandas`, `matplotlib` y `networkx`, en un ambiente virtual (la primera celda del notebook también los instala):

  ```bash
  python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```

> ⚠️ **Bajen el contenedor del Lab 08 antes de levantar este.** Es el mismo contenedor (`pmd-neo4j`): si sigue arriba, `docker compose up` falla con *container name "/pmd-neo4j" is already in use*. Desde esta carpeta: `docker compose -f ../08/docker-compose.yml down -v`.

## Neo4j en un contenedor

Imagen oficial `neo4j:5-community` (versión probada: **Neo4j 5.26.32**, la LTS de la serie 5). Los datos quedan en el volumen `pmd-neo4jdata`.

```bash
docker compose up -d --wait                                     # levantar y esperar a que acepte consultas (30-60 s)
open http://localhost:7474                                      # Neo4j Browser (Windows/Linux: ábranlo en el navegador)
docker compose exec neo4j cypher-shell -u neo4j -p pmd2026neo   # consola de Cypher
docker compose down                                             # apagar (el grafo queda en el volumen)
docker compose down -v                                          # ... y borrar el volumen
```

| Puerto | Qué |
|---|---|
| `7474` | Neo4j Browser (HTTP): <http://localhost:7474> |
| `7687` | Bolt: por donde hablan el driver de Python y `cypher-shell` |

La carpeta `import/` se monta en `/var/lib/neo4j/import` dentro del contenedor: ahí busca `LOAD CSV` cuando se le pide `'file:///archivo.csv'`.

Credenciales: usuario `neo4j`, clave `pmd2026neo`. No es secreta: el contenedor es local. La clave se fija al crear el volumen; si `up --wait` termina en *unhealthy* tras ~2–3 minutos, casi siempre es un volumen viejo con otra clave → `docker compose down -v` y repetir.

## Los datos

**El grafo base** es el del Lab 08, cargado con el mismo script (`01_cargar_grafo.cypher`): 12 paradas, 7 comunas y 4 líneas.

```
(:Parada {id, nombre, lat, lon})-[:EN]->(:Comuna {nombre})
(:Linea {id, nombre})-[:PASA_POR {orden}]->(:Parada)
(:Parada)-[:SIGUE_A {linea, minutos}]->(:Parada)     // en el sentido de la línea
```

| Línea | Nombre | Paradas | Minutos por tramo |
|---|---|---|---|
| L1 | Concepción–Talcahuano | Plaza Perú → Mall del Trébol → Parque Pedro del Río → Terminal Talcahuano | 12, 8, 10 |
| L2 | Concepción–Penco | Universidad de Concepción → Plaza Perú → Barrio Norte → Plaza Penco | 6, 7, 18 |
| L3 | Collao–Lomas Coloradas | Terminal Collao → Universidad de Concepción → Plaza Chiguayante → Lomas Coloradas | 9, 15, 14 |
| L4 | Concepción–Coronel | Plaza Perú → Puente Llacolén → Lomas Coloradas → Plaza Coronel | 9, 11, 20 |

La Parte 1 del notebook **borra todo y recarga** el script cada vez (y borra el índice del Ej. 5 si quedó), para que las respuestas no dependan de una corrida anterior.

**La ampliación** se carga en la Parte 2 desde los 4 CSV de `import/` (UTF-8): una parada nueva, **P13 Hospital Regional**, y una línea exprés **L5 Express Talcahuano–Penco** que pasa por ella. Son datos sintéticos de pocas líneas y por eso, excepcionalmente, se versionan en el repo: no hay nada que descargar.

| Archivo | Qué trae |
|---|---|
| `paradas_ext.csv` | P13 (nueva) y P07, P10 (ya existen) |
| `lineas_ext.csv` | la línea L5 |
| `pasa_por_ext.csv` | por qué paradas pasa la L5, en orden |
| `tramos_ext.csv` | los 2 tramos de la L5, con sus minutos (28 y 22) |

Esperado tras cargar los cuatro: Parada 13 · Comuna 7 · Linea 5 · EN 13 · PASA_POR 19 · SIGUE_A 14. Cargarlos dos veces no cambia nada. **El orden importa:** primero `paradas_ext`; después líneas, `PASA_POR` y tramos.

## Sin Python (ruta alternativa)

Todo es Cypher puro. Si el driver de Python no funciona en su máquina:

```bash
docker compose up -d --wait
docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo < 01_cargar_grafo.cypher
```

Después, peguen en el Browser (o en `cypher-shell`) los `LOAD CSV` de la Parte 2 y el Cypher de cada ejercicio, sin el `q("""…""")`. Para los planes del Ej. 5, antepongan `PROFILE` a la consulta: el Browser lo dibuja. Copien desde el notebook, no desde el PDF de las diapositivas: las comillas tipográficas dan errores de sintaxis raros.

## Archivos

| Archivo | Qué es |
|---|---|
| `lab09_estudiantes.ipynb` | el notebook del laboratorio |
| `lab09_docente.ipynb` | con soluciones (no se versiona) |
| `01_cargar_grafo.cypher` | crea las restricciones y carga el grafo base (el mismo del Lab 08) |
| `docker-compose.yml` | el servicio `pmd-neo4j`, con volumen (el mismo del Lab 08) |
| `import/` | los 4 CSV de la ampliación, montados en el contenedor para `LOAD CSV` |
| `requirements.txt` | dependencias del ambiente virtual |
