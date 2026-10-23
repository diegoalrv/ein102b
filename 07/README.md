# Laboratorio 07 — HBase, cuando los datos ya no caben en memoria (para trabajar en casa)

> Material de estudio para trabajar en casa: no se entrega ni se evalúa, y HBase no entra en el Certamen (sí sirve para la Tarea 2 y el proyecto). **Orden recomendado:** leer `CONTENTS.md` (esta carpeta) y después hacer el notebook. Cuenten con 2–3 horas.

Segunda mitad del bloque de streaming. El stream del Lab 06 guarda ~7 horas en RAM; hoy la historia va a disco, en HBase: una semana del mismo generador (~1,2 millones de lecturas), dos diseños de row key, *hotspotting* medido por región, el camino de escritura (WAL → MemStore → HFile → compaction) visto en el volumen y, si el VPS conecta, un consumidor stream → HBase.

## Qué se necesita

- **Docker** con `docker compose` y **~4 GB de RAM** asignados (Docker Desktop → Settings → Resources), más ~3 GB de disco (imagen 1,2 GB + datos ~1,5 GB).
- La imagen `pmd-hbase`, construida una vez, antes de abrir el notebook:

  ```bash
  docker compose build    # descarga HBase 2.5.15 de Apache (~340 MB): una vez por máquina
  ```

- Python con `happybase`, `redis` y `pandas`, en un ambiente virtual:

  ```bash
  python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```

- La carpeta `../06/` (el notebook importa `generador.py` de ahí) y, solo para la Parte 5, su `.env` con la clave del VPS.

> ⚠️ **Construyan la imagen antes de abrir el notebook:** la descarga (~340 MB) y el `build` tardan unos minutos. Si la construcción falla o la red es lenta, se puede copiar la imagen desde otra máquina: `docker save pmd-hbase | gzip > pmd-hbase.tar.gz` y, en la otra, `docker load < pmd-hbase.tar.gz`.

## La Parte 5 (opcional): del stream a HBase

Lee en vivo el stream compartido del Lab 06 (el del VPS) y lo guarda en su HBase local. Necesita, en `../06/.env`, la clave del VPS que les envía el profesor y un `EQUIPO` **único** (por ejemplo `nombre-apellido`): se usa como nombre de su consumer group, `ingesta-<EQUIPO>`, y si dos personas repiten el nombre comparten el grupo y se reparten los eventos. Si el VPS no responde, el notebook lo avisa y pueden saltarse la Parte 5: el resto del laboratorio no depende de ella.

## HBase en un contenedor

No hay imagen oficial de HBase en Docker Hub, así que se construye (`Dockerfile`): Java 11 + HBase 2.5.15 en modo **standalone** — HMaster, RegionServer y ZooKeeper en un solo proceso, guardando en el volumen `pmd-hbase` en vez de HDFS. Las ideas son las de un cluster; la escala, la de un PC.

```bash
docker compose up -d --wait               # levantar y esperar a que HBase responda (30-60 s)
docker compose exec hbase hbase shell     # la consola de HBase
docker compose down                       # apagar (los datos quedan en el volumen)
docker compose down -v                    # ... y borrar el volumen (PC compartido)
```

| Puerto | Qué |
|---|---|
| `9090` | Thrift: por donde habla `happybase` |
| `16010` | interfaz web del HMaster: <http://localhost:16010> (tablas, regiones, métricas en `/jmx`) |

## Archivos

| Archivo | Qué es |
|---|---|
| `CONTENTS.md` | el material de estudio: léanlo antes del notebook |
| `lab07_estudiantes.ipynb` | el notebook del laboratorio |
| `lab07_docente.ipynb` | con soluciones (no se versiona) |
| `Dockerfile` | HBase 2.5.15 standalone + Thrift |
| `docker-compose.yml` | el servicio `pmd-hbase`, con volumen |
| `requirements.txt` | dependencias del ambiente virtual |
