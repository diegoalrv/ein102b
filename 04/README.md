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

Recargar `comunas_cl.sql` son 218 MB de `INSERT`s y tarda cerca de un minuto. Es local, no de red.

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
- El cero silencioso del 21-ago fue eso mismo funcionando **demasiado bien**: `&&` compara cajas sin mirar el SRID, y las cajas de una capa en grados y otra en metros no se rozan nunca (Ejercicio 3.2). El embudo se vacía en la fase 1 y `_ST_Contains` jamás se ejecuta — por eso no hubo error.

Conviene dejarlos anotar los dos tiempos en la pizarra (**SIN ÍNDICE** / **CON ÍNDICE**) antes de explicar nada. El factor sale de dividir dos números que ellos midieron.

## Resultados esperados

Los conteos con `puntos_masivos` **cambian en cada equipo**: `random()` va sin semilla. Es deseable —se compara la forma del plan, no el número— pero hay que decirlo en voz alta o alguien va a creer que se equivocó. Para reproducibilidad, el notebook trae comentado un `SELECT setseed(0.42)`.

Lo que sí es determinista:

- **1.1** `intersects=t · disjoint=f · overlaps=t · touches=f · contains_p=t · within_p=t · crosses_l=t`.
- **1.2** la forma A entrega el conteo por comuna (**16** estaciones distribuidas, **4** sin comuna — los mismos números del 4.1 del Lab 03); la forma B entrega **cero filas**, sin error: un punto no puede contener un polígono.
- **1.3** los centroides que caen fuera son los de comunas cóncavas o multiparte (Valparaíso con sus islas, Juan Fernández, Isla de Pascua). Para un punto garantizado dentro, `ST_PointOnSurface`.
- **2.2** `Seq Scan on puntos_masivos`: se leen las 500.000 filas y cada una se evalúa contra un `MultiPolygon` de miles de vértices. Varios segundos. ⟨completar con el tiempo del equipo docente⟩
- **2.3** el plan cambia a `Bitmap Index Scan on idx_puntos_geom` + `Bitmap Heap Scan` con `Recheck Cond`. Uno o dos órdenes de magnitud menos. ⟨completar⟩
- **2.4** con el índice prohibido, el tiempo vuelve al del 2.2 — la ganancia es del índice, no de la caché.
- **3.1** el conteo con solo `&&` es **mayor** que el de `ST_Contains`: la diferencia son los falsos positivos (mar, cerros).
- **3.2** una caja en el rango `(-71, -33)` y otra en `(250000, 6300000)`. No se rozan.
- **3.3** mismo conteo, planes distintos (`Seq Scan` vs `Index Scan`) y una diferencia de tiempo grande. ⟨completar⟩
- **4.1** `Index Scan using idx_puntos_geom` con `Order By:`. **4.2** sin `LIMIT`, el plan vuelve a `Seq Scan` + `Sort`.
- **Anexo** sobre la DPA 2023 cargada como en el Lab 03: **0 geometrías inválidas**. El dataset viene limpio, así que `ST_MakeValid` se demuestra sobre un "corbatín" escrito a mano.

> ⚠️ Los números de 1.2 y del anexo son los verificados el 20-ago sobre la DPA 2023. Si se cambia la versión del dataset, reejecutar.

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
- **El volumen borrado:** lo esperable, y está cubierto — pero la recarga de `comunas_cl` tarda ~1 min por máquina. Si arrancan 25 equipos a la vez, contarlo en los 10 minutos de la Parte 0.

## Checklist previa del profesor

- [ ] Correr el notebook docente de punta a punta en un equipo del laboratorio y **anotar los tiempos reales** (2.2, 2.3, 3.3) para completar los `⟨completar⟩` de arriba y del libreto
- [ ] Medir cuánto demora `CREATE INDEX` sobre 500.000 puntos en una máquina del laboratorio; si supera ~30 s, bajar el enunciado a 200.000
- [ ] Verificar en cada máquina que existan `01/muestra_A.geojson` y `03/datos/comunas_cl.sql` (la Parte 0 los necesita si el volumen no sobrevivió, que es lo normal)
- [ ] Confirmar que la imagen `postgis/postgis:16-3.4` siga descargada tras la limpieza del 21-ago
- [ ] Preparar la pizarra con dos casillas grandes: **SIN ÍNDICE** / **CON ÍNDICE**
- [ ] Tener lista la planilla de recepción de propuestas del proyecto (equipo · dataset · familias · preguntas)
- [ ] Generar las diapositivas con el libreto de `Clases/Clase 4 (2808)` en Claude Design
