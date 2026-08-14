# Laboratorio 02 — Clase 2 (Vie 14-ago): Docker en serio y primeros pasos con PostGIS

> Material práctico de la sesión. El libreto de las diapositivas está en `Clases/Clase 02/Libreto_Clase2_ClaudeDesign.md` (relativo a la raíz del curso, fuera de este repositorio). El enunciado del proyecto semestral —que se presenta en la cátedra de esta clase— está en `Proyecto/Enunciado_Proyecto_Semestral.md`.

## Qué se necesita

Este laboratorio **no tiene datos propios**: reutiliza la muestra A del Lab 01 (`../01/muestra_A.geojson`). Si no existe:

```bash
cd ../01 && python3 generar_muestras.py
```

Además de lo del Lab 01, hoy se usan:

```bash
pip install sqlalchemy psycopg2-binary
```

Y la imagen de Docker del bloque:

```bash
docker pull postgis/postgis:16-3.4
```

> ⚠️ **Descargar la imagen ANTES de la clase** (o al llegar): son ~215 MB de descarga (~850 MB ya desempacada en disco), y 25 equipos bajándola a las 08:30 saturan la red del laboratorio. En Apple Silicon la imagen es amd64 pura, sin variante arm64: el `pull` no reclama, pero el `run` avisa de la plataforma y corre emulada — funciona bien (arranca en ~3 s). Para silenciar el aviso, `--platform linux/amd64` en el `run`.

## Estructura de la sesión

| Parte | Bloque | Contenido |
|---|---|---|
| 1 — Docker de verdad | 1–2 (08:25–09:25) | Imagen vs contenedor, puertos, `docker run` con PostGIS, y el experimento de la persistencia: contenedores desechables vs volúmenes |
| 2 — Mini-ETL | 3 (09:40–09:55) | Extraer (`muestra_A.geojson`) → Transformar (WKT) → Cargar (`ST_GeomFromText`) |
| 3 — La pregunta pendiente | 3 (09:55–10:05) | `ST_Contains`, `ST_DWithin`, `ST_Distance`: por fin se responde *"¿qué estaciones están dentro de la zona de restricción?"* |
| 4 — Síntesis | 10:05–10:15 | Tabla de conceptos + 2 ideas de dataset como semilla del proyecto |

Convenciones del laboratorio: contenedor `pmd-postgis`, clave `pmd2026`, puerto **5433** (para no chocar con un Postgres local; si está ocupado, cambiar a 5434 en el `run` **y** en la `URL` del notebook), volumen `pmd-pgdata`.

Dos cosas que aparecen en máquinas compartidas: si el `run` responde `name already in use`, quedó un contenedor de otra sesión (`docker rm -f pmd-postgis` y repetir); y si sobrevivió el volumen `pmd-pgdata` con otra clave, `POSTGRES_PASSWORD` se ignora y la conexión falla con *password authentication failed* (borrar el volumen). Desde Docker 29, `docker images` ya no tiene columna `SIZE`: muestra `CONTENT SIZE` (lo que se descarga) y `DISK USAGE` (lo que ocupa desempacada).

## El giro del 3.1 (no spoilear)

La consulta `ST_Contains` de la zona de restricción devuelve **cero estaciones** — y es a propósito: los datos son así (se verifica con el mapa del Lab 01 y con `ST_Intersects`, porque la ruta del metro sí cruza la zona). La discusión que importa: *resultado vacío ≠ consulta mala*, y "cerca" no es "adentro" (el 3.2 lo resuelve con `ST_DWithin`). Los resultados numéricos esperados están en el notebook docente, verificados contra PostGIS 3.4.

## Notebooks

- `lab02_estudiantes.ipynb` — el del laboratorio. 12 celdas con `# Escribe tu código aquí`.

La versión docente (soluciones, tiempos por bloque y respuestas esperadas) no está en este repositorio.

## Al terminar (máquinas compartidas)

```bash
docker rm -f pmd-postgis
docker volume rm pmd-pgdata
```

La imagen puede quedar: se reutiliza cuando parta el bloque geoespacial (21-ago).

## Checklist restante (de la página de Notion)

- [ ] Dejar `postgis/postgis:16-3.4` descargada en las máquinas del laboratorio **antes** del viernes
- [ ] Verificar que `sqlalchemy` y `psycopg2-binary` estén instalados en las máquinas (o que haya red para el `pip install`)
- [ ] Generar diapositivas con el libreto (`Clases/Clase 02/Libreto_Clase2_ClaudeDesign.md`) en Claude Design
- [ ] Publicar el enunciado del proyecto en el repositorio del curso
