# Laboratorio 05 — Clase 5 (Vie 04-sep): PostGIS de punta a punta

> Material práctico de la sesión. El libreto de las diapositivas está en `Clases/Clase 5 (0409)/Clase 5 (0409) — Libreto.md` y la guía docente en `Clases/Clase 5 (0409)/Clase 5 (0409) — Laboratorio 05.md` (relativos a la raíz del curso, fuera de este repositorio).

Tercera y última sesión del bloque geoespacial. Las dos anteriores enseñaron a **representar** (Lab 03) y a **consultar con índices** (Lab 04). Esta arma el recorrido completo con datos reales de OpenStreetMap — fuente → GeoPackage → `ogr2ogr` → PostGIS → capas derivadas → consultas → mapa y exportación — y deja la infraestructura declarada en un `docker-compose.yml`. Es, en chico, la parte geoespacial del proyecto semestral, y el molde de la **Tarea 1**.

Ese día también se conversa la **propuesta del proyecto** con cada equipo, durante la práctica: el notebook está escrito para que los equipos avancen solos mientras el profesor rota.

## Qué se necesita

Tres cosas que deben existir **antes** de la clase, en cada máquina:

| Qué | De dónde | Cómo |
|---|---|---|
| `../01/muestra_A.geojson` | Lab 01 | `cd ../01 && python3 generar_muestras.py` |
| `../03/datos/comunas_cl.sql` | Lab 03 | `cd ../03 && python3 preparar_datos.py` (necesita el ZIP de la DPA en `03/datos_fuente/`) |
| `datos/osm_gran-valparaiso.gpkg` | **nuevo**: extracto de OSM | `python3 preparar_datos.py` (necesita `chile-latest.osm.pbf` en `datos_fuente/`) — o copiar el `.gpkg` ya generado en otra máquina |

Y la imagen `pmd-postgis-gdal`, que se construye una vez con `docker compose build` (el `Dockerfile` de esta carpeta: el PostGIS de siempre + `gdal-bin` + las utilidades de cliente de PostGIS). `preparar_datos.py` la construye solo si no encuentra `ogr2ogr` en la máquina; si la máquina tiene GDAL instalado, hay que correr `docker compose build` a mano igual, porque el notebook usa `ogr2ogr` **dentro del contenedor**.

### El extracto de OpenStreetMap

OSM no se descarga entero (el planeta son ~80 GB). Geofabrik publica extractos por país, actualizados a diario, con licencia ODbL:

- Ficha: <https://download.geofabrik.de/south-america/chile.html>
- Descarga: <https://download.geofabrik.de/south-america/chile-latest.osm.pbf> (**~330 MB**, verificado el 02-sep-2026; no hay subregiones de Chile)

El `.osm.pbf` va **tal cual** en `datos_fuente/`. Después:

```bash
python3 preparar_datos.py
```

Eso recorta la caja del Gran Valparaíso (lon −71,75…−71,33 · lat −33,16…−32,88: Valparaíso, Viña del Mar, Concón, Quilpué y Villa Alemana), reproyecta a SIRGAS-Chile / UTM 19S (5361) y deja `datos/osm_gran-valparaiso.gpkg` con tres capas (`points`, `lines`, `multipolygons`). Lo hace con `ogr2ogr` — el de la máquina si existe, si no el de la imagen del curso — y termina verificando el GeoPackage por dentro (es un SQLite) con una línea así:

```
Verificación OK: N puntos · N líneas · N polígonos · SRID 5361 → osm_gran-valparaiso.gpkg (N MB)
```

Si no ves esa línea, algo falló y el notebook no va a funcionar. Sin argumentos respeta lo que ya exista; con `--forzar` rehace todo. El script no tiene dependencias de Python. La conversión lee el archivo completo de Chile una vez (unos minutos, con barra de progreso).

> ⚠️ **Todo esto va ANTES de la clase.** Son 330 MB por máquina desde Geofabrik, más la construcción de la imagen (un `apt-get` dentro de Docker): 25 equipos haciéndolo a las 08:30 saturan la red, exactamente como el 14-ago y como el ZIP de la DPA. Dos atajos válidos: (1) copiar entre máquinas el `.gpkg` ya generado — pesa mucho menos que el `.pbf` y es lo único que la clase necesita; (2) hacer `docker compose build` en cada máquina el día anterior, que es el único paso con red que no se puede copiar.

### Camino de rescate: sin `ogr2ogr` en clase

Si en alguna máquina la imagen no se construyó (sin red, sin permisos), `preparar_datos.py --sql` deja además `datos/osm_gran-valparaiso.sql` en formato PGDump, que se carga con el `psql` del contenedor de siempre, sin GDAL:

```bash
docker compose exec -T db psql -q -U postgres -d postgres -f /datos/osm_gran-valparaiso.sql
```

Con eso las Partes 2 a 4 funcionan igual; se pierde el Ejercicio 1.2 (la carga la hizo el script) y las exportaciones del 4.2 (que usan `ogr2ogr`). El `.sql` pesa bastante más que el `.gpkg`.

### Otras zonas

El script acepta otras cajas. Son las que usa la Tarea 1 (y las que un equipo puede querer para su proyecto):

```bash
python3 preparar_datos.py --zona santiago-centro          # la zona de la Tarea 1
python3 preparar_datos.py --zona gran-concepcion
python3 preparar_datos.py --bbox -70.75 -33.52 -70.52 -33.36 --nombre mi-zona
```

## Convenciones

Las mismas desde el Lab 02 — contenedor `pmd-postgis` · puerto **5433** · volumen `pmd-pgdata` · `postgres`/`pmd2026`/`postgres` — pero ahora declaradas en `docker-compose.yml` en vez de escritas en un `docker run`. La imagen cambia: `pmd-postgis-gdal`, construida desde `postgis/postgis:16-3.4`. El nombre del contenedor y del volumen se mantienen a propósito: los notebooks de los labs anteriores siguen funcionando contra este contenedor.

El contenedor **ve** tres carpetas de la máquina (montajes en el compose): `./datos` → `/datos`, `../01` → `/labs/01` y `../03/datos` → `/labs/03`. Se acabó el `docker cp`.

Tablas nuevas de hoy: `osm_puntos`, `osm_lineas`, `osm_poligonos` (crudas, del cargador) y `calles`, `edificios`, `paraderos`, `amenidades`, `comunas_sub` (derivadas) más la vista materializada `mv_densidad`.

## Estructura de la sesión

| Parte | Bloque | Contenido |
|---|---|---|
| 0 — De `docker run` a `docker compose` | 1 (08:15–08:30) | El compose leído en voz alta; `up --wait`; reconstrucción del escenario sin `docker cp` |
| 1 — Extraer y cargar | 1 (08:30–08:55) | `ogrinfo` sobre el GeoPackage; `ogr2ogr` a PostGIS con `-lco`; interrogar lo cargado; `other_tags` como hstore; geometrías inválidas de OSM y `ST_MakeValid` |
| 2 — Transformar | 2 (08:55–09:25) | Capas derivadas con esquema propio; edificios por comuna (punto interior vs polígono); grilla hexagonal + vista materializada |
| *Recreo* | — | *09:25–09:40* |
| 3 — Consultar | 3 (09:40–10:05) | Cobertura de paraderos (anti-join con `ST_DWithin`); farmacia más cercana (LATERAL); km de calle por comuna y `ST_Subdivide`; índices sin uso y `VACUUM ANALYZE` |
| 4 — Salida | 3 (10:05–10:15) | Mapa con matplotlib desde GeoJSON; exportar a GeoPackage/GeoJSON con `ogr2ogr`; `pg_dump` |
| 5 — Síntesis | 10:15 | La tabla del pipeline: hoy vs. su proyecto |
| Cátedra | 10:15–10:50 | Cierre del bloque, el ecosistema, **Tarea 1** |

## El hilo del día (no spoilear)

La sesión entera es **una sola tubería** contada de izquierda a derecha, y cada parte cobra una deuda de las clases anteriores:

- **Parte 0** cobra el Lab 02: el `docker run` de cinco flags era información que merecía un archivo. `docker compose` es el mismo comando, declarado. El montaje de carpetas reemplaza al `docker cp` del Lab 03.
- **Parte 1** cobra el Lab 03: `ogr2ogr` es `shp2pgsql` generalizado (200+ formatos), y `-t_srs` / `-lco SPATIAL_INDEX=GIST` son el `-s` y el `-I` de entonces. El GeoPackage es el "reemplazo moderno del shapefile" que la diapositiva 16 prometió. Y el anexo del Lab 04 se cumple: OSM **sí** trae geometrías inválidas, y `ST_PointOnSurface` revienta con ellas — por eso se repara antes de derivar, y se documenta.
- **Parte 2** es la T de ETL hecha en SQL: de tablas crudas a capas con nombre. El punto interior (`ST_PointOnSurface`, del 1.3 del Lab 04) resuelve el doble conteo en los bordes comunales; la vista materializada es la decisión "materializar vs. calcular" del Lab 04 (Parte 0), ahora con nombre propio.
- **Parte 3** son tres patrones del proyecto: anti-join (`NOT EXISTS` + `ST_DWithin`), vecino más cercano por fila (LATERAL, del 4.3 del Lab 04) y el costo de un polígono gigante (`ST_Subdivide`: cajas chicas → menos falsos positivos, la Parte 3 del Lab 04 aplicada al revés).
- **Parte 4** cierra el círculo: el mismo `ogr2ogr` que trajo los datos los saca, en el formato del destinatario (diapositiva 16 de la Clase 3).

## Resultados esperados

**Estado de verificación (03-sep):** el pipeline completo — `preparar_datos.py` (recorte + reproyección + verificación + `--sql`), la carga con `ogr2ogr` y `COLUMN_TYPES=other_tags=hstore`, y **todas las celdas de código del notebook** — se ejecutó de punta a punta contra PostGIS 3.4.2 / PostgreSQL 16 / GDAL 3.8.4 con un extracto de prueba de OSM (no Chile: la máquina de verificación no tenía acceso a Geofabrik) y una `comunas_cl` sintética. Lo que está verificado es que el código corre y que los planes tienen la forma descrita. **Los conteos y tiempos del Gran Valparaíso están marcados ⟨medido⟩ y hay que completarlos corriendo el notebook docente con el `.gpkg` real** — ver checklist.

- **Parte 0** con el volumen borrado: reconstrucción completa en ~10 s (igual que el Lab 04; ahora `psql -f /labs/03/comunas_cl.sql` sin `docker cp`). `docker compose up -d --wait` espera al healthcheck (`pg_isready`), así que `esperar_postgres` debería acertar al primer intento.
- **1.1** `ogrinfo -so` lista tres capas con `PROJCRS["SIRGAS-Chile / UTM zone 19S"`. Conteos ⟨medido⟩ — los mismos que imprimió `preparar_datos.py`.
- **1.2** tres cargas; la de `multipolygons` es la lenta. Tiempos ⟨medido⟩ (en el extracto de prueba, 13.000 objetos cargaron en ~1 s; el Gran Valparaíso debería ser cientos de miles de objetos y del orden de decenas de segundos a un par de minutos).
- **1.3** dos índices por tabla, `*_pkey` (B-tree) y `*_geom_geom_idx` (GiST): ninguno lo creamos a mano. En `osm_puntos` el índice pesa comparable a los datos; en `osm_poligonos`, mucho menos.
- **1.4** en la capa de puntos `amenity` **no** es columna (vive en `other_tags`); en polígonos sí. `highway` sí es columna en líneas y puntos. Es la configuración por defecto del driver OSM de GDAL (`osmconf.ini`). Los conteos de `bus_stop` y `pharmacy` ⟨medido⟩.
- **1.5** `NOT ST_IsValid` **sí** devuelve filas en OSM (en el extracto de prueba, 50 de 1.095 polígonos, casi todas `Self-intersection`). La reparación `ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))` deja 0 inválidos y puede dejar algunos **vacíos** (área 0), que la Parte 2 excluye con `NOT ST_IsEmpty`. Sin este paso, `CREATE TABLE edificios` falla con `lwgeom_pointonsurface: GEOS Error: IllegalArgumentException` — verificado.
- **2.1** conteos ⟨medido⟩. `ANALYZE` al final es obligatorio: sin él, el 2.2 puede elegir un plan malo.
- **2.2** plan: `Nested Loop Left Join` con `Seq Scan on comunas_cl` (38 filas, filtradas por `cut_reg`) afuera e `Index Scan using idx_edificios_punto` adentro, con **`Index Cond: (punto @ c.geom)`** — el operador `@` ("caja contenida en caja") es la fase 1 en versión contención — y `Filter: st_contains(...)` como fase 2. Con `ST_Intersects(c.geom, e.geom)` el índice pasa a `idx_edificios_geom` con `&&`, y el total de edificios **sube**: los que cruzan un límite se cuentan en dos comunas (verificado en la prueba: 482 con punto vs. 559 con polígono). Ninguna versión es "la mala": son preguntas distintas.
- **2.3** `ST_HexagonGrid(500, caja)` sobre la caja de **los edificios**, no de las comunas: la caja de `comunas_cl` va desde Isla de Pascua (x ≈ −3,7 millones, el bicho del Lab 03) y generaría millones de hexágonos vacíos. `ST_Extent` devuelve `box2d` sin SRID: hay que envolverlo en `ST_SetSRID`. Hexágonos y máximo ⟨medido⟩.
- **3.1** el `NOT EXISTS` aparece como `SubPlan` con `Index Scan using idx_paraderos_geom` e `Index Cond: (geom && st_expand(e.punto, 400))` — el índice se usa del lado **de adentro** (paraderos), una búsqueda por edificio. Porcentajes ⟨medido⟩; lo esperable es que Viña salga mejor cubierta y las comunas con expansión de parcelas (Quilpué, Villa Alemana) peor. Recordar en voz alta: son paraderos **dibujados en OSM**.
- **3.2** el LATERAL funciona igual que en el Lab 04; las estaciones sobre el mar / rurales deberían quedar arriba de la lista.
- **3.3** `ST_Subdivide(geom, 128)` sobre 345 comunas produce miles de partes de ≤128 vértices; la consulta de km por comuna debería acelerarse entre 5× y 20× ⟨medido⟩ con los **mismos** kilometrajes (la unión de las partes es la comuna). No sirve como reemplazo de `comunas_cl` para nada que trate a la comuna como un objeto (área, centroide, `count(DISTINCT)`).
- **3.4** `idx_edificios_geom` debería salir con pocas o cero lecturas (todo se hizo por `punto`). `VACUUM` no admite transacción: por eso la celda abre una conexión en `AUTOCOMMIT`. `pg_stat_user_indexes` puede ir con unos segundos de retraso.
- **4.1** el mapa se dibuja con matplotlib desde GeoJSON (`ST_AsGeoJSON(ST_Transform(geom, 4326))` + `to_jsonb(q) - 'geom'` para las propiedades): sin instalar folium ni geopandas, que no están en las máquinas. La densidad debería marcar el plan de Valparaíso y Viña y el eje Quilpué–Villa Alemana.
- **4.2** `ogr2ogr` con `PG:` como **origen** y `-sql`: primer `ogr2ogr` crea el GeoPackage, el segundo lo abre con `-update` para agregar una capa. El GeoJSON se exporta con `-t_srs EPSG:4326` porque el estándar lo exige.
- **4.3** `pg_dump -Fc -t …` desde dentro del contenedor, hacia `/datos`. Tamaño ⟨medido⟩; compararlo con el `.gpkg` de entrada.

## Notebooks

- `lab05_estudiantes.ipynb` — el del laboratorio. Celdas dadas para la plomería (Parte 0), las cargas (1.2), la reparación (1.5), las capas derivadas (2.1), la higiene (3.4) y toda la Parte 4; el resto es `# Escribe tu código aquí`.
- La versión docente (soluciones, respuestas esperadas y tiempos) no está en este repositorio.

## Al terminar (máquinas compartidas)

```bash
docker compose down -v
```

Borra el contenedor y el volumen `pmd-pgdata`. La **imagen** y `datos/osm_gran-valparaiso.gpkg` se quedan: sin ellos no hay Parte 0 rápida la próxima vez. Los archivos de salida (`resultados_*.gpkg`, `densidad_*.geojson`, `respaldo_geo.dump`) los borra la última celda del notebook.

## Riesgos conocidos

- **Red:** el `.pbf` (330 MB) y el `docker compose build` van antes de la clase. En clase, cero descargas.
- **`docker compose` ausente:** Docker Desktop lo trae; en un Linux con `docker-ce` viejo puede faltar el plugin. La celda de configuración lo detecta. Plan B: `docker run` como en el Lab 04 (mismo nombre de contenedor, mismo volumen, agregar `-v $(pwd)/datos:/datos -v $(pwd)/../01:/labs/01:ro -v $(pwd)/../03/datos:/labs/03:ro`) y la imagen `pmd-postgis-gdal` construida con `docker build -t pmd-postgis-gdal .`.
- **Imagen no construida:** sin `gdal-bin` no hay `ogrinfo`/`ogr2ogr` → usar el camino de rescate (`--sql` + `psql -f`) y saltar 1.1, 1.2 y 4.2.
- **Disco:** el `.gpkg` más las tablas (crudas + derivadas + índices) más `comunas_cl` pueden sumar 1–2 GB por máquina. Si aprieta, `preparar_datos.py --bbox` con una caja más chica (por ejemplo solo Valparaíso–Viña: `-71.68 -33.10 -71.48 -32.95`) y **anotarlo**; las conclusiones no cambian.
- **Extracto distinto por máquina:** `chile-latest` cambia a diario. Si las máquinas se prepararon en días distintos, los conteos difieren entre equipos. Es deseable decirlo antes de que alguien crea que se equivocó — y es un buen pie para el bloque de streaming: el dato que cargamos es una **foto** de algo que cambia todo el tiempo.
- **Puerto 5433 ocupado / volumen de otro proyecto:** compose usa `container_name` y `name:` fijos, así que convive con lo que dejaron los labs anteriores. Si hay otro contenedor `pmd-postgis` levantado con la imagen vieja, `compose up` lo recrea con la nueva (los datos del volumen se conservan).

## Checklist previa del profesor

- [ ] Descargar `chile-latest.osm.pbf` (330 MB) una vez, correr `python3 preparar_datos.py` y **anotar la línea de verificación** (conteos reales del Gran Valparaíso)
- [ ] `docker compose build` en la máquina propia; verificar `docker compose exec db ogr2ogr --version`
- [ ] Correr `lab05_docente.ipynb` de punta a punta y **completar los ⟨medido⟩** del notebook docente, del README y del libreto (tiempos de carga, conteos, factor de `ST_Subdivide`, porcentajes de cobertura, hexágono más denso)
- [ ] Repetir en una máquina del laboratorio (x86, sin emulación) y medir el tiempo total de la Parte 0 + 1.2
- [ ] Distribuir a las 25 máquinas: el `.gpkg` (copiándolo a `05/datos/`) y la imagen (`docker compose build` por máquina, o `docker save`/`docker load` si la red del lab no aguanta 25 `apt-get`)
- [ ] Verificar en cada máquina `01/muestra_A.geojson` y `03/datos/comunas_cl.sql`
- [ ] Decidir el orden de la ronda de propuestas y tenerlo en la pizarra al empezar (5 min por equipo, tres preguntas: ¿tocaron el dataset?, ¿dónde se cruzan las familias?, ¿cuál es el riesgo?)
- [ ] Tener listo el enunciado de la **Tarea 1** para publicarlo al cierre (`Tareas/Tarea 1/`)
- [ ] Generar las diapositivas con el libreto de `Clases/Clase 5 (0409)` en Claude Design
