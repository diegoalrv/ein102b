# Laboratorio 03 — Clase 3 (Vie 21-ago): Representación de datos geoespaciales

> Material práctico de la sesión. El libreto de las diapositivas está en `Clases/Clase 03/Libreto_Clase3_ClaudeDesign.md` (relativo a la raíz del curso, fuera de este repositorio).

Primera sesión del bloque geoespacial. Se salda la deuda del Lab 02: la columna `comuna` de la muestra A estaba inventada, y hoy se verifica contra las comunas oficiales de Chile.

## Qué se necesita

A diferencia de los Labs 01 y 02, aquí los datos **no se generan**: son reales y públicos.

**División Política Administrativa 2023** — IDE Chile (SUBDERE · IGM · DIFROL · INE), publicada en datos.gob.cl con licencia CC-BY. **345 comunas** (Chile tiene 346: el producto no cubre el Territorio Antártico — material de discusión del 2.3), escala 1:50.000, SIRGAS-Chile **geográfico** (grados, EPSG:5360), formato shapefile.

- Ficha: <https://datos.gob.cl/dataset/categoria-geoespacial-limites-y-fronteras>
- Descarga directa: <https://www.geoportal.cl/geoportal/catalog/download/912598ad-ac92-35f6-8045-098f214bd9c2>

El ZIP descargado va **sin descomprimir** en `datos_fuente/`. Después:

```bash
python3 preparar_datos.py
```

Eso hace tres cosas: extrae el shapefile de comunas a `datos/COMUNAS.*`, verifica lo que el notebook docente promete, y genera `datos/comunas_cl.sql` corriendo `shp2pgsql` desde la imagen `postgis/postgis:16-3.4-alpine` — porque la imagen del laboratorio (la Debian de siempre) trae el motor pero **no** las utilidades de cliente. Al final imprime algo así:

```
Verificación OK: 345 comunas del país (la Antártica no viene en la DPA) · 38 en la Región de Valparaíso · SRID 5360 → carga en 5361
  → comunas_cl.sql (218 MB) — reproyectado de 5360 (grados) a 5361 (UTM 19S, metros)
```

Si no ves esas líneas, algo falló y el notebook no va a funcionar. Sin argumentos respeta lo que ya exista; con `--forzar` rehace todo. El script no tiene dependencias de Python (lee el `.shp`, el `.dbf`, el `.prj` y el `.cpg` con la biblioteca estándar), pero **sí usa Docker** para el paso de `shp2pgsql`.

> ⚠️ **Todo esto va ANTES de la clase, en cada máquina.** El ZIP son **~311 MB** desde geoportal.cl, y la imagen alpine otros ~90 MB: 25 equipos bajándolos a las 08:30 saturan la red del laboratorio — exactamente el problema del 14-ago con la imagen de Docker. Por eso el script **no** descarga el ZIP por su cuenta, y por eso `comunas_cl.sql` se genera en la preparación: en clase, la carga es un `psql -f` sin red.

Además se reutiliza la muestra A del Lab 01 (`../01/muestra_A.geojson`). Si falta:

```bash
cd ../01 && python3 generar_muestras.py
```

Nada nuevo que instalar en el host respecto del Lab 02: `pandas`, `sqlalchemy`, `psycopg2-binary` y la imagen `postgis/postgis:16-3.4`, que debería seguir en las máquinas desde el 14-ago (la limpieza del Lab 02 borra el contenedor y el volumen, no la imagen).

## Estructura de la sesión

| Parte | Bloque | Contenido |
|---|---|---|
| 0 — Reconstruir el escenario | 1 (08:15–08:25) | Plomería: levantar PostGIS con volumen y recargar la muestra A del Lab 01 |
| 1 — Cuatro vestidos | 1 (08:25–08:50) | WKT, EWKT, WKB, GeoJSON; interrogar geometrías (`ST_GeometryType`, `ST_SRID`, `ST_NPoints`); construir desde texto |
| 2 — Datos reales | 2 (08:50–09:25) | El shapefile por fuera (`.shp` + amigos), carga con el SQL de `shp2pgsql`, exploración de las 345 comunas |
| *Recreo* | — | *09:25–09:40* |
| 3 — La trampa | 3 (09:40–09:55) | El join por SRID mixto que devuelve **cero filas sin error**; `spatial_ref_sys`; `ST_Transform` |
| 4 — El cruce | 3 (09:55–10:10) | Atributo declarado vs. geometría; los `NULL` del `LEFT JOIN`; áreas y el dominio de validez de una proyección |
| 5 — Síntesis | 10:10–10:15 | Tabla de conceptos + recordatorio de la propuesta del proyecto (28-ago) |

Convenciones (las mismas del Lab 02): contenedor `pmd-postgis`, clave `pmd2026`, puerto **5433**, volumen `pmd-pgdata`, imagen `postgis/postgis:16-3.4`. Tabla nueva de hoy: `comunas_cl`.

Como la limpieza del 14-ago borró el volumen, las tablas `estaciones` y `referencias` **no** están: la Parte 0 las recarga desde `../01/muestra_A.geojson`. Va como celda dada, corrida de una sola vez.

## El giro del 3.1 (no spoilear)

La DPA llega en grados (5360), pero la carga del 2.2 la normaliza a la proyección de trabajo en metros (5361, SIRGAS-Chile / UTM 19S) — la práctica normal de cualquier organización. Las estaciones siguen en 4326. Con eso queda armada la trampa: el *spatial join* con `ST_Contains` entre `estaciones` (grados) y `comunas_cl` (metros) devuelve **cero filas, sin error y sin advertencia**. Y esta vez la consulta **sí** está mala — al revés que el 14-ago, donde el resultado vacío era el dato correcto.

La razón es concreta y vale explicarla en la pizarra: `ST_Contains(a,b)` se expande a `a && b AND _ST_Contains(a,b)`. El operador `&&` compara **cajas envolventes** y no valida el SRID; como una capa está en grados y la otra en metros, las cajas no se solapan nunca y ningún par llega a la comprobación real. Suelto, sin `JOIN`, no hay `&&` que filtre y el error sí aparece: *`contains: Operation on mixed SRID geometries (MultiPolygon, 5361) != (Point, 4326)`*.

Lo que tienen que llevarse no es `ST_Transform` —eso es fácil— sino el reflejo de **mirar `ST_SRID` antes de cruzar dos capas**. Conviene dejarlos un rato con el cero antes de dar la pista.

## Resultados esperados

Verificados el 20-ago ejecutando el notebook docente completo contra el ZIP oficial (PostGIS 3.4, PostgreSQL 16):

- **1.1** WKT 26 caracteres · GeoJSON 52 · WKB 21 bytes. El EWKB añade `20 e6100000`: el flag de SRID y el 4326.
- **1.2** `ZON-001` es `ST_Polygon` con **5** vértices (el anillo cierra repitiendo el primero); `RUT-014` es `ST_LineString` con 4.
- **2.3** **345** comunas (¡no 346: falta la Antártica!) · **38** en la Región de Valparaíso (`cut_reg = '05'` — es texto) · un solo tipo, `ST_MultiPolygon` · SRID 5361 · **0 geometrías inválidas**. Con más partes en la región: Isla de Pascua (171) y Juan Fernández (30); a nivel país, Natales (15.772 — fiordos).
- **3.1** el join sin transformar → **0 filas**, sin error. **3.2** extensiones: estaciones en grados (x ≈ -71,6), comunas en metros (x de -3.700.812 a 407.484 — el x negativo es Isla de Pascua proyectada desde lejos). **3.3** con `ST_Transform` de las estaciones → **16 filas**.
- **4.1** de 20 estaciones: **4 coinciden**, **12 no coinciden**, **4 no caen en ninguna comuna**.
- **4.2** las cuatro sin comuna caen sobre el mar: Forestal (394 m de Viña del Mar), Curauma (1.753 m), Rodelillo (2.073 m, ambas de Viña del Mar) y Miraflores Alto (2.677 m de Valparaíso).
- **4.3** Isla de Pascua: **245,6 km²** medida en UTM 19S contra **163,9 km²** sobre el elipsoide — **50% de error** por proyectar a 3.700 km del meridiano central de la zona. La columna `superficie` oficial de la DPA (163,85) coincide con el elipsoide.

> ⚠️ Estos números son de la DPA **2023** descargada el 20-ago-2026. Si se cambia la versión del dataset, reejecutar el notebook docente de punta a punta: los conteos del 4.1/4.2 dependen de dónde caen los bordes comunales.

## Notebooks

- `lab03_estudiantes.ipynb` — el del laboratorio. 15 celdas de código, con `# Escribe tu código aquí`.

La versión docente (soluciones, tiempos por bloque y respuestas esperadas) no está en este repositorio.

## Al terminar (máquinas compartidas)

```bash
docker rm -f pmd-postgis
docker volume rm pmd-pgdata
```

Las imágenes pueden quedar: la del lab se reutiliza el 28-ago con los índices espaciales.

## Checklist restante (de la página de Notion)

- [ ] Descargar el ZIP de la DPA 2023 (~311 MB) y dejarlo en `datos_fuente/` **en cada máquina** del Lab. de Informática 2, antes del viernes
- [ ] En cada máquina: `docker pull postgis/postgis:16-3.4-alpine` y `python3 preparar_datos.py` (deja `datos/COMUNAS.*` y `datos/comunas_cl.sql` listos; necesita red)
- [ ] Verificar que la imagen `postgis/postgis:16-3.4` siga descargada tras la limpieza del 14-ago
- [ ] Generar diapositivas con el libreto (`Clases/Clase 03/Libreto_Clase3_ClaudeDesign.md`) en Claude Design — el libreto ya quedó corregido el 20-ago con los números verificados (345 comunas, carga `5360:5361`, UTF-8, 4 estaciones al mar)
- [x] Correr el notebook docente de punta a punta con el ZIP oficial (hecho el 20-ago; incluye Docker y el SQL de `shp2pgsql`)
- [x] Confirmar el SRID que reporta `preparar_datos.py` (5360 geográfico; la carga reproyecta a 5361 y `SRID_ORIGEN` ya no existe en el notebook)
