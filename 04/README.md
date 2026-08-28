# Laboratorio 04 — Clase 4 (Vie 28-ago): Lenguajes de consulta geoespaciales e índices espaciales

Segunda sesión del bloque geoespacial. Se responde la pregunta que quedó abierta el 21-ago: qué hizo realmente ese `-I` de `shp2pgsql`, y por qué una consulta espacial sin índice no escala.

Ese día también se recibe la **propuesta del proyecto semestral** (equipo · dataset · familias · preguntas), durante la Parte 0.

## Qué se necesita

**Nada nuevo que descargar.** El dato masivo de hoy —500.000 puntos— se **genera dentro de la base** con `generate_series` y `random()`. La red del laboratorio no se toca.

Lo que sí hace falta es el escenario de las clases anteriores, que la Parte 0 arma sola:

| Tabla | Viene de | SRID | Filas |
|---|---|---|---|
| `estaciones` | `../01/muestra_A.geojson` | 4326 | 20 |
| `comunas_cl` | `../03/datos/comunas_cl.sql` | 5361 | 345 |

En el caso ideal esas dos tablas siguen vivas en el volumen `pmd-pgdata` y la Parte 0 solo hace `docker start`. Pero el Lab 03 termina pidiendo `docker volume rm pmd-pgdata` (máquinas compartidas), así que **lo normal es que el volumen no esté**: la Parte 0 detecta qué falta y lo reconstruye desde el material de los Labs 01 y 03. Por eso los dos archivos de la tabla tienen que existir antes de empezar. Si falta alguno:

```bash
cd ../01 && python3 generar_muestras.py     # muestra_A.geojson
cd ../03 && python3 preparar_datos.py       # comunas_cl.sql (necesita el ZIP de la DPA en 03/datos_fuente/)
```

La celda de verificación **falla ruidosamente** con un `assert` si el escenario no queda exacto. Si no imprime `Verificación OK: 20 estaciones (SRID 4326) · 345 comunas (SRID 5361)`, no sigan: los conteos de toda la mañana dependen de eso.

Recargar `comunas_cl.sql` son 218 MB de `INSERT`s, pero es local y rápido: la reconstrucción completa —contenedor nuevo, estaciones y comunas— **medida son 10 s**. No es de red.

## Convenciones (las mismas desde el Lab 02)

Contenedor `pmd-postgis` · imagen `postgis/postgis:16-3.4` · puerto **5433** · volumen `pmd-pgdata` · usuario/clave/base `postgres`/`pmd2026`/`postgres`.

Tablas nuevas de hoy: `estaciones_5361` (la capa chica reproyectada de una vez) y `puntos_masivos`.

## Estructura de la sesión

| Parte | Bloque | Contenido |
|---|---|---|
| 0 — Levantar y verificar | 1 (08:15–08:25) | Plomería + recepción de propuestas del proyecto |
| 1 — El catálogo de predicados | 1 (08:25–08:50) | Los predicados sobre geometrías de juguete; el orden de los argumentos; medidas y constructores |
| 2 — El costo de no indexar | 2 (08:50–09:25) | 500.000 puntos, `EXPLAIN ANALYZE` sin índice, `CREATE INDEX ... USING GIST`, y el experimento de control |
| *Recreo* | — | *09:25–09:40* |
| 3 — El filtro en dos fases | 3 (09:40–10:00) | `&&` desnudo, falsos positivos, el cero silencioso del 21-ago explicado, `ST_DWithin` vs `ST_Distance` |
| 4 — Vecino más cercano | 3 (10:00–10:10) | `<->`, la detención temprana y el `CROSS JOIN LATERAL` |
| 5 — Síntesis | 10:10–10:15 | El factor medido, el diagnóstico del SRID y una consulta del proyecto |
| Anexo | si sobra | `ST_IsValid` / `ST_MakeValid` |

## El giro del día (no spoilear)

Toda la sesión converge en una sola idea: `ST_Contains(a, b)` **no es una función**, es azúcar para `a && b AND _ST_Contains(a, b)`. De ahí salen las tres conclusiones de la mañana, que son la misma vista de tres lados:

- El índice acelera **porque** la fase 1 (`&&`, cajas contra cajas) descarta casi todo antes de la parte cara (Parte 2).
- El índice es **correcto** porque `&&` puede dar falsos positivos pero nunca falsos negativos: la caja siempre contiene a la geometría (Ejercicio 3.1).
- El cero silencioso del 21-ago fue eso mismo funcionando **demasiado bien**: `&&` compara cajas sin mirar el SRID, y las cajas de una capa en grados y otra en metros no se tocan (Ejercicio 3.2). El embudo se vacía en la fase 1 y `_ST_Contains` jamás se ejecuta — por eso no hubo error.

Detalle que conviene tener medido antes de decirlo en la pizarra: las dos cajas **sí se solapan en `x`** (Isla de Pascua proyectada arrastra el `xmin` de las comunas a −3.700.812, y −71 cae dentro de ese rango). Lo que las separa es `y`. Basta un eje, pero si uno afirma de memoria que "no se tocan en nada", el dato lo desmiente.

Conviene dejarlos anotar los dos tiempos en la pizarra (**SIN ÍNDICE** / **CON ÍNDICE**) antes de explicar nada. El factor sale de dividir dos números que ellos midieron.

## Resultados esperados

**Verificados el 27-ago ejecutando el notebook completo** (PostGIS 3.4 / PostgreSQL 16) contra el escenario del Lab 03. Los tiempos son de un MacBook con la imagen `postgis/postgis:16-3.4`, que es **amd64 y corre emulada** en Apple Silicon: en las máquinas x86 del laboratorio deberían ser mejores. Vuelvan a medirlos ahí; lo que no cambia es el **orden de magnitud** y la forma de los planes.

Los conteos sobre `puntos_masivos` **cambian en cada equipo**: `random()` va sin semilla. Es deseable —se compara la forma del plan, no el número— pero hay que decirlo en voz alta o alguien va a creer que se equivocó. Para reproducibilidad, el notebook trae comentado un `SELECT setseed(0.42)`. Los números de abajo son de una corrida de ejemplo.

- **1.1** `intersects=t · disjoint=f · overlaps=t · touches=f · contains_p=t · within_p=t · crosses_l=t`. Los `AS` son **obligatorios**: `overlaps` es palabra reservada y sin `AS` la consulta no compila.
- **1.2** forma A: **6 comunas**, **16 estaciones** repartidas (Viña del Mar 5, Limache 4, Quilpué 3, Valparaíso 2, Concón 1, Villa Alemana 1) y **4** que no caen en ninguna — los mismos 16/4 del 4.1 del Lab 03. Forma B: **cero filas**, sin error.
- **1.3** en la Región de Valparaíso el centroide cae fuera en exactamente **2** comunas: **Juan Fernández** (30 partes) y **Calera** (una sola parte, pero cóncava). Ojo: Valparaíso e Isla de Pascua **no** están en esa lista, aunque sean multiparte — tener varias partes no implica que el centroide caiga fuera. Para un punto garantizado dentro, `ST_PointOnSurface`.
- **2.2** el plan **no** es un `Seq Scan` a secas: es `Parallel Seq Scan on puntos_masivos` (500.000 filas en 3 procesos) del lado de afuera, y del lado de adentro un `Index Scan using comunas_cl_geom_idx` con `loops=500000` — el índice que dejó `shp2pgsql -I` el 21-ago, usado medio millón de veces. **~2.100 ms**, de los cuales **~1.600 ms son JIT**: PostgreSQL compila la consulta porque la estima cara. Vale avisarlo antes de que alguien divida los tiempos.
- **2.3** `CREATE INDEX` + `ANALYZE`: **0,6 s**. El plan pasa a `Bitmap Index Scan on idx_puntos_geom` + `Bitmap Heap Scan`, y desaparece el JIT. **~21 ms → factor ~100×.** Índice **20 MB** sobre una tabla de 53 MB.
  > ⚠️ Bajo el `Bitmap Heap Scan` **no** aparece un `Recheck Cond`, sino `Filter: st_contains(...)` con `Rows Removed by Filter: ~9.600`. Esas filas descartadas son exactamente los falsos positivos que explica la Parte 3 — conviene señalarlas aquí y cobrar la deuda en el 3.1. (El `Recheck Cond` sí aparece en el 3.1, donde la condición del índice es el `&&` desnudo.)
- **2.4** ⚠️ **el control no hace lo que promete el libreto.** Con los índices prohibidos el tiempo **no vuelve** al del 2.2: da **~138 ms**, seis veces más lento que el 2.3 pero quince veces más rápido que el 2.2. La razón es buena y da para tres minutos de pizarra: `enable_indexscan = off` apaga *todos* los índices, incluido el de `comunas_cl`, así que el planificador ya no puede armar el nested loop de 500.000 iteraciones del 2.2 y elige un plan mejor (un `Seq Scan` con `Join Filter`). **Lo que el ejercicio sí demuestra sigue en pie**: con todo caliente en caché y sin índice la consulta es 6× más lenta, o sea la ganancia no es de la caché. Lo que **no** demuestra es que prohibir un índice equivalga a no tenerlo — el planificador cambia de estrategia, y ese es el aprendizaje que se llevan. El notebook ya pregunta por esto en el 2.4.3 y 2.4.4.
- **3.1** solo `&&` → **17.091** filas; con `_ST_Contains` → **7.361**. **~9.700 falsos positivos, el 57%**: la caja de Valparaíso incluye mucho mar y cerro. Ahí aparece el `Recheck Cond: (c.geom && geom)`.
- **3.2** las cajas medidas:
  - `estaciones` (4326) → `BOX(-71.60977 -33.09225, -71.34553 -32.97154)`
  - `comunas_cl` (5361) → `BOX(-3700811.8 3734030.99, 705965.8 8065247.05)`

  **Cuidado con el discurso fácil:** en el eje **x** las dos cajas **sí se solapan** (el −3.700.812 es Isla de Pascua proyectada a 3.700 km del meridiano central — el mismo bicho del 4.3 del Lab 03, y −71 cae dentro de ese rango). Lo que las separa es el eje **y**: −33 contra 3,7–8,1 millones. Basta con que **un** eje no se toque para que `&&` sea falso, y eso es justamente lo que hay que hacerles notar.
- **3.3** mismo conteo en las dos versiones (**69** en la corrida de ejemplo). `ST_Distance < 1000` → `Parallel Seq Scan`, **~640 ms** (otra vez con JIT). `ST_DWithin` → `Bitmap Index Scan` con `Index Cond: (geom && ST_Expand(e.geom, 1000))` — el filtro en dos fases a la vista— y **0,3 ms**. **Factor ~1.900×**, el más espectacular del día.
  > La estación se llama **`Estación Muelle Prat`**, no `Muelle Prat`. Con el nombre a medias la consulta devuelve cero filas sin error: el mismo síntoma del 21-ago, ahora por un `WHERE` que no calza.
- **3.4** `ST_Buffer` da **el mismo conteo** que `ST_DWithin` (69) y usa el índice igual, pero tarda **~6 ms** contra 0,3: **20× más lento** solo por construir el polígono. El predicado le gana al constructor.
- **4.1** `Index Scan using idx_puntos_geom` con `Order By:`, **0,3 ms**. **4.2** sin `LIMIT` el plan cambia a `Gather Merge` + `Sort` (`Sort Method: external merge Disk: ~12 MB`) + `Parallel Seq Scan`: **~296 ms, mil veces más lento**. La ganancia era la detención temprana.
- **4.3** el `CROSS JOIN LATERAL` funciona y devuelve la estación más cercana a cada uno de los 10 puntos.
- **Anexo** `NOT ST_IsValid(geom)` sobre la DPA 2023 → **0 filas**. El dataset viene limpio, así que `ST_MakeValid` se demuestra sobre el "corbatín": `POLYGON((0 0, 10 10, 10 0, 0 10, 0 0))` es inválido (`Self-intersection[5 5]`), tiene **área 0**, y reparado pasa a ser un `ST_MultiPolygon` de **área 50**. Que una reparación cambie el área de 0 a 50 es el argumento de por qué se documenta.

> ⚠️ Los conteos de 1.2, 1.3 y el anexo dependen de la DPA **2023**. Si se cambia la versión del dataset, reejecutar.

### Lo que costó cada paso (misma máquina)

| Paso | Tiempo |
|---|---|
| Parte 0 con el volumen vivo (`docker start` + verificación) | 0,1 s |
| Parte 0 reconstruyendo todo (contenedor nuevo + estaciones + 218 MB de comunas) | **10 s** |
| 2.1 — `CREATE TABLE` de 500.000 puntos | 0,3 s |
| 2.3 — `CREATE INDEX` + `ANALYZE` | 0,6 s |

Es decir: **la Parte 0 aguanta perfectamente los 10 minutos** aunque el volumen se haya borrado, y ni la generación de los 500.000 puntos ni el índice son un riesgo de tiempo. El riesgo del enunciado era el disco, no el reloj.

## Notebooks

- `lab04_estudiantes.ipynb` — el del laboratorio. Celdas dadas para la plomería (Parte 0 y la generación de los 500.000 puntos); el resto es `# Escribe tu código aquí`.

La versión docente (soluciones y tiempos medidos) no está en este repositorio.

## Al terminar (máquinas compartidas)

```bash
docker rm -f pmd-postgis
docker volume rm pmd-pgdata
```

Medio millón de puntos más su índice no son para dejarlos en un equipo compartido. Y no hay nada que perder: la Parte 0 reconstruye el escenario desde cero.

## Riesgos conocidos

- **Disco:** 500.000 puntos + índice pueden apretar máquinas con poco espacio libre. Plan B: bajar `N_PUNTOS` a 200.000 en la celda del 2.1 y anotarlo — la conclusión no cambia, solo la magnitud.
- **Caché:** la segunda ejecución de cualquier consulta se ve más rápida por la caché del sistema. Para eso está el Ejercicio 2.4.
- **`random()` sin semilla:** conteos distintos por equipo. Decirlo en voz alta.
- **El volumen borrado:** lo esperable, y está cubierto: la reconstrucción completa medida son **10 s**, dentro de los 10 minutos de la Parte 0.
- **Puerto 5433 ocupado:** si la máquina ya tiene otro PostgreSQL publicado en 5433, `docker run` falla con `port is already allocated`. Se resuelve cambiando el `-p` y la `URL` del notebook, o apagando el otro contenedor.

## Checklist previa del profesor

- [x] Correr el notebook de punta a punta y anotar los tiempos (hecho el 27-ago en un Mac; **repetir en una máquina del laboratorio**, que es x86 y no emula la imagen)
- [x] Medir `CREATE INDEX` sobre 500.000 puntos: **0,6 s** — no hace falta bajar a 200.000 por tiempo (el riesgo sigue siendo el disco)
- [ ] Verificar en cada máquina que existan `01/muestra_A.geojson` y `03/datos/comunas_cl.sql` (la Parte 0 los necesita si el volumen no sobrevivió, que es lo normal)
- [ ] Confirmar que la imagen `postgis/postgis:16-3.4` siga descargada tras la limpieza del 21-ago
- [ ] Preparar la pizarra con **tres** casillas: **SIN ÍNDICE** / **CON ÍNDICE** / **ÍNDICE PROHIBIDO** — el tercer número es el del 2.4 y no cae donde uno espera
- [ ] Tener lista la planilla de recepción de propuestas del proyecto (equipo · dataset · familias · preguntas)
- [ ] Generar las diapositivas con el libreto de `Clases/Clase 4 (2808)` en Claude Design
