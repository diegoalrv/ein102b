# Laboratorio 08 — Clase 11 (Vie 23-oct): Neo4j I, pensar en grafos (para trabajar en casa)

> La Clase 11 fue online y demostrativa: los ejercicios se vieron en vivo. Este laboratorio lo hacen en casa, a su ritmo; no se entrega ni se evalúa, pero conviene hacerlo antes de la Clase 12, que parte de este mismo grafo. Cuenten con 1,5–2 horas.

*Libreto: `Clases/Clase 11 (2310)/Clase 11 (2310) — Libreto.md` · guía docente: `Clases/Clase 11 (2310)/Clase 11 (2310) — Laboratorio 08.md` (en la carpeta del curso, fuera de este repositorio).*

Primera sesión del bloque de grafos. Con Redis y HBase preguntábamos por clave; hoy la pregunta es «¿con quién se conecta esto?». Se trabaja sobre una red **sintética** de 12 paradas de micro del Gran Concepción, con 7 comunas y 4 líneas: patrones de uno y varios saltos, transbordos, `CREATE` / `MERGE` / `DETACH DELETE`, el grado de cada parada y la dirección de las relaciones.

## Qué se necesita

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

> ⚠️ **Descarguen la imagen antes de abrir el notebook:** sin ella, `docker compose up` la baja en ese momento y tarda varios minutos. Si la red es lenta, se puede copiar la imagen desde otra máquina: `docker save neo4j:5-community | gzip > neo4j.tar.gz` y, en la otra, `docker load < neo4j.tar.gz`.

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

Cómo consultar directo al contenedor (la consola `cypher-shell`, consultas sueltas desde la terminal, cargar archivos y el Browser): `CONTENTS.md`.

Credenciales: usuario `neo4j`, clave `pmd2026neo`. No es secreta: el contenedor es local. La clave se fija al crear el volumen; si `up --wait` termina en *unhealthy* tras ~2–3 minutos, casi siempre es un volumen viejo con otra clave → `docker compose down -v` y repetir.

## El grafo

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

`01_cargar_grafo.cypher` crea todo (12 paradas, 7 comunas, 4 líneas) y se carga **una sola vez**: si se repite, choca con las restricciones de unicidad. Para empezar de cero: `MATCH (n) DETACH DELETE n` y cargar de nuevo.

## Sin Python (ruta alternativa)

Los ejercicios son Cypher puro. Si el driver de Python no funciona en su máquina:

```bash
docker compose up -d --wait
docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo < 01_cargar_grafo.cypher
```

(o peguen el archivo completo en el Browser). Después, peguen en el Browser el Cypher de cada celda del notebook, sin el `q("""…""")`. Copien desde el notebook o desde el `.cypher`, no desde el PDF de las diapositivas: las comillas tipográficas dan errores de sintaxis raros.

## Archivos

| Archivo | Qué es |
|---|---|
| `CONTENTS.md` | cómo consultar Neo4j directo al contenedor, sin Python |
| `lab08_estudiantes.ipynb` | el notebook del laboratorio |
| `lab08_docente.ipynb` | con soluciones (no se versiona) |
| `01_cargar_grafo.cypher` | crea las restricciones y carga el grafo |
| `docker-compose.yml` | el servicio `pmd-neo4j`, con volumen |
| `import/` | carpeta montada en el contenedor para `LOAD CSV` (Clase 12) |
| `requirements.txt` | dependencias del ambiente virtual |
