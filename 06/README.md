# Laboratorio 06 — Clase 7 (Vie 25-sep): Redis, datos en memoria y streaming

> Material práctico de la sesión. El libreto está en `Clases/Clase 7 (2509)/Clase 7 (2509) — Libreto.md` y la guía docente en `Clases/Clase 7 (2509)/Clase 7 (2509) — Laboratorio 06.md` (relativos a la raíz del curso, fuera de este repositorio). El material de estudio es `CONTENTS.md`, en esta carpeta.

Primera sesión del bloque de streaming: estructuras de Redis, Pub/Sub (que pierde lo que no escuchó) y Streams con consumer groups (que lo guardan y lo reparten). Los datos son 16 sensores sintéticos del Gran Concepción, ~2 eventos por segundo.

## Qué se necesita

- Python con `redis`, `pandas` y `pyarrow`, en un ambiente virtual:

  ```bash
  python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```

  y elegir el kernel de `.venv` en Jupyter / VS Code.
- **Docker** con `docker compose`, solo para el camino de rescate.
- `datos/gran_concepcion_stream.parquet`, solo para el camino de rescate: `python3 generador.py --parquet` (no se versiona; también se puede copiar de otra máquina, pesa ~200 KB).

## Conexión: el `.env`

```bash
cp .env.example .env     # y completar VPS_PASS con la clave que se da en clase (y EQUIPO)
```

El notebook lee host, puerto, clave y equipo desde ahí: la clave nunca queda en el código ni en git.

## Dos caminos, los mismos datos

| | Stream compartido (VPS) | Camino de rescate (local) |
|---|---|---|
| Redis | `redis-stream.5.75.154.51.sslip.io:443`, con TLS; la clave se da en clase | `pmd-redis` en `localhost:6379` (`docker-compose.yml`) |
| Fuente | `generador.py` corriendo en el servidor | el notebook reproduce el parquet |
| Parte 3 | todo el curso en el mismo consumer group | 2–3 consumidores dentro del equipo |

El notebook elige solo (Parte 0): prueba el VPS por 3 segundos y, si no conecta, levanta el Redis local. Ambos caminos usan `eventos()` de `generador.py` con la misma semilla, así que se ven idénticos.

El VPS va por el puerto **443** (el de HTTPS) a propósito: es el que casi cualquier red deja salir. En el VPS, los alumnos no pueden borrar el stream, hacer `FLUSHALL` ni `XADD` (ACL de Redis); todo lo demás del laboratorio funciona.

```bash
H=redis-stream.5.75.154.51.sslip.io
redis-cli -h $H -p 443 --tls --sni $H -a <clave>     # probar la conexión a mano (sin --sni, falla la verificación TLS)
docker compose up -d --wait                                              # camino de rescate a mano
```

### Plan B: servidor de emergencia en la sala

Si el VPS falla, los equipos caen solos al camino de rescate y siguen trabajando. Mientras, el profesor levanta el mismo servidor (Redis con la misma ACL + generador) en su PC del laboratorio:

```bash
GEN_PASS=<cualquier clave> docker compose -f docker-compose.emergencia.yml up -d --wait
ipconfig getifaddr en0          # la IP a dar al curso (Windows: ipconfig)
docker compose -p pmd-emergencia down   # apagar
```

La clave de alumnos la toma del `.env`. Los equipos ponen `VPS_HOST=<IP>` y `VPS_PORT=6379` en su `.env` (con un puerto distinto de 443 el notebook no usa TLS), reinician el kernel y vuelven a tener un stream compartido para la Parte 3. En Windows hay que aceptar el aviso del firewall para el puerto 6379.

## Archivos

| Archivo | Qué es |
|---|---|
| `lab06_estudiantes.ipynb` | el notebook de la clase |
| `lab06_docente.ipynb` | con soluciones (no se versiona) |
| `generador.py` | el generador del VPS y del parquet |
| `docker-compose.yml` | el Redis del camino de rescate (efímero, sin volumen) |
| `docker-compose.emergencia.yml` | Plan B: el servidor compartido, en el PC del profesor |
| `requirements.txt` | dependencias del ambiente virtual |
| `.env.example` | variables de conexión: copiar como `.env` y completar la clave (el `.env` no se versiona) |
| `CONTENTS.md` | material de estudio de la clase |
