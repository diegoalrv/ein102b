# Contenidos — HBase: cuando los datos ya no caben en memoria

**Curso:** Procesamiento Masivo de Datos (ELE051-B / EIN102B) · Paralelo 701 · 2026-2
**Bloque Streaming + NoSQL (2 y 3 de 4) · Material para trabajar en casa · octubre de 2026**

> Material de estudio, escrito para alguien que **nunca ha usado HBase**. Cada comando se explica antes o después de usarse — dónde se escribe, qué hace cada palabra y qué se espera ver como respuesta. Los números que aparecen como "medido" salieron de una corrida de verificación del Laboratorio 07 en un Mac con Docker; en su computador los tiempos serán distintos, pero los conteos y las proporciones no. Si algo acá no coincide con lo que ven, avisen al canal del curso.

**Cómo usar este documento con el Laboratorio 07.** Lean las secciones 1 a 5 antes de abrir el notebook; la sección 6 antes de la Parte 2; la 7 y la 9 antes de la Parte 3; la 8 antes de la Parte 4; la 11 antes de la Parte 5.

| Sección de este documento | Parte del Laboratorio 07 |
|---|---|
| 1–3: el problema, por qué HBase, qué es | (contexto) |
| 4: cómo se usa | Parte 0: levantar HBase |
| 5: el modelo de datos | Parte 1: tablas, `put`, `get`, versiones |
| 6: la row key es el índice | Parte 2: cargar la semana, `scan` por rango y filtro |
| 7 y 9: regiones y *hotspotting* | Parte 3: la misma semana, otra row key |
| 8: el camino de escritura | Parte 4: `flush`, `major_compact`, apagar y prender |
| 11: Redis, HBase y PostGIS | Parte 5: del stream a HBase, y Parte 6: síntesis |

---

## 1. El problema: la historia no cabe en memoria

En el laboratorio de Redis guardaron las lecturas de 16 sensores del Gran Concepción en un *stream*: un registro al que se le agregan eventos al final, a razón de unos 2 por segundo. Redis es muy rápido porque guarda todo en la memoria RAM. Pero la RAM es cara y limitada, y por eso el stream del curso está configurado para recortarse solo, y guarda apenas las últimas ~7 horas.

Hagamos la cuenta con números medidos (1 de octubre) sobre el mismo stream:

- 50.000 entradas ocupan unos **4,4 MB** de RAM, es decir, **~88 bytes por entrada**.
- A 2 eventos por segundo, 50.000 entradas son **~7 horas** (50.000 ÷ 2 = 25.000 s).
- Si quisiéramos guardar **5 años** de esos mismos sensores: 2 eventos/s × 86.400 s/día × 365 días × 5 años ≈ **315 millones** de entradas. Multiplicadas por 88 bytes, son **~28 GB de RAM**.
- Y eso es con **16 sensores**. Una ciudad real tiene miles.

Ustedes pueden comprobar el dato de los 88 bytes en el notebook del Lab 06, en una celda de Python con la conexión `r` ya abierta:

```python
r.memory_usage("sensores:flujo") / r.xlen("sensores:flujo")   # bytes por entrada
```

- `r.memory_usage("sensores:flujo")` pregunta a Redis cuántos bytes de RAM ocupa esa clave.
- `r.xlen("sensores:flujo")` pregunta cuántas entradas tiene el stream.
- La división da el promedio de bytes por entrada.

La pregunta que abre esta clase es entonces: **si lo que no cabe en RAM no cabe en Redis, ¿dónde guardamos la historia?** Lo que se necesita es una base de datos que:

1. **escriba muy rápido y sin pausa**, porque los eventos siguen llegando;
2. **guarde en disco**, que es barato y grande;
3. **se reparta entre muchas máquinas**, para crecer agregando máquinas en vez de cambiar la que ya hay;
4. **lea bien por rangos** ("todo lo de esta estación entre las 9 y las 10"), que es la pregunta típica de los datos que llegan en el tiempo.

## 2. ¿Y por qué no simplemente PostgreSQL?

Es una buena pregunta, porque PostgreSQL (con PostGIS) ya la conocen, y es una base excelente. La respuesta honesta no es "PostgreSQL no puede": con buen hardware, particionamiento y cuidado, aguanta mucho más de lo que parece. La respuesta es que **sus decisiones de diseño apuntan a otra cosa**:

- Los índices de PostgreSQL son **B-trees**. Para mantenerlos ordenados, cada inserción modifica páginas del índice *en su lugar*, en posiciones dispersas del disco. Con miles de inserciones por segundo sostenidas durante años, eso significa **escritura aleatoria** casi sin descanso.
- Una base relacional tradicional vive en **una máquina**. Cuando ese servidor llega a su techo de disco o de CPU, no se "agrega otro": hay que rediseñar (réplicas, particiones, sharding a mano).
- A cambio, PostgreSQL les da cosas valiosas: SQL, joins, transacciones entre tablas, índices secundarios, restricciones de integridad, geometría con PostGIS.

HBase hace el intercambio contrario: **renuncia a muchas de esas comodidades para poder escribir secuencialmente y crecer repartiendo los datos entre máquinas.** No es "mejor": es la herramienta para el caso en que lo que importa es tragarse un río de datos que no para y poder leerlo después por clave o por rango.

## 3. Qué es HBase

> **HBase es un mapa ordenado gigante, repartido entre muchas máquinas y guardado en disco.**

- Está inspirado en **Bigtable**, el sistema que Google describió en un artículo científico en 2006 (presentado en la conferencia OSDI). HBase es la versión de código abierto, mantenida por la Apache Software Foundation.
- En un cluster real corre sobre **HDFS**, el sistema de archivos distribuido de Hadoop: un sistema que parte cada archivo en bloques y guarda varias copias de cada bloque (por defecto **3**) en máquinas distintas, de modo que si una máquina se cae, los datos siguen en las otras.
- Está pensado para **miles de millones de filas** y **millones de columnas**, en hardware común.
- Lo usan donde predominan **escrituras masivas** y lecturas **por clave o por rango**: mensajería, series de tiempo, registros (*logs*), historiales de sensores.
- Se clasifica como base de datos **NoSQL** de tipo *wide-column* (columnas anchas, agrupadas en familias). Ojo con el nombre: no es lo mismo que una base "columnar" para análisis, como las que se usan en bodegas de datos. Más abajo se ve exactamente qué significa.

**En el laboratorio no hay cluster.** Usamos HBase en modo **standalone**: el maestro (HMaster), el servidor de datos (RegionServer) y ZooKeeper corren juntos en **un solo proceso**, dentro de un contenedor Docker, y guardan en una carpeta del disco del contenedor en vez de HDFS. Las **ideas** son las de un cluster; la **escala**, la de un PC. Más adelante, en cada sección, se dice qué cambia en un cluster de verdad.

## 4. Cómo se usa HBase, paso a paso

### 4.1 El modelo: un servicio, y clientes que le hablan

Igual que Redis, HBase no es una librería que se importa: es un **servicio** que queda corriendo y al que uno se **conecta**. Por dentro tiene varias piezas (se explican en la sección 7), pero para usarlo basta saber que hay:

- **El servicio**, que en el laboratorio vive dentro del contenedor `pmd-hbase`.
- **Clientes** que le mandan órdenes. Para este laboratorio usarán **dos**:
  - **`hbase shell`** — una consola interactiva donde se escriben comandos a mano y se ve la respuesta al tiro. Es la mejor forma de *aprender* los comandos.
  - **`happybase`** — una librería de Python (`import happybase`) con la que el notebook habla con HBase desde código. No habla directo con HBase, sino con un servidor intermedio llamado **Thrift** (un traductor), que en el laboratorio escucha en el **puerto 9090**.
- Además hay una **página web de monitoreo** en <http://localhost:16010> (la interfaz del HMaster), donde se ven las tablas, sus regiones y métricas. Conviene dejarla abierta mientras trabajan.

### 4.2 Levantar HBase con Docker

Todos estos comandos se escriben en la **terminal de su computador** (Terminal en Mac y Linux; PowerShell en Windows), **dentro de la carpeta `Laboratorios/07`**. No son comandos de HBase ni de Python.

```bash
docker compose build
```

- Construye la imagen `pmd-hbase`: descarga Java y HBase 2.5.15 desde Apache (~340 MB) y los empaqueta. **Se hace una sola vez**, y necesita internet. No existe una imagen oficial de HBase en Docker Hub, por eso hay que construirla.

```bash
docker compose up -d --wait
```

- `up` crea y arranca el contenedor. `-d` lo deja corriendo "de fondo" (la terminal queda libre). `--wait` hace que el comando **espere** hasta que HBase esté realmente listo (la primera vez, entre 30 y 60 segundos), en vez de volver apenas el contenedor existe.

```bash
docker compose exec hbase hbase shell
```

- Abre la **consola de HBase** dentro del contenedor. `exec` ejecuta un programa dentro de un contenedor que ya corre; `hbase` es el nombre del servicio (como aparece en `docker-compose.yml`); `hbase shell` es el programa.

```bash
docker compose down        # apaga y borra el contenedor; los datos QUEDAN en el volumen
docker compose down -v     # ... y además borra el volumen (todos los datos)
```

- Un **volumen** es una carpeta de Docker que sobrevive aunque el contenedor se borre. Aquí se llama `pmd-hbase` y es donde HBase guarda sus datos: por eso, **al revés que el Redis del Lab 06, apagar y prender HBase no pierde nada** (lo comprueban en el ejercicio 4.4). `down -v` es la "limpieza": libera ~1,5 GB.

### 4.3 La consola `hbase shell`

Al abrirla, el prompt cambia a algo parecido a:

```
hbase:001:0>
```

Esa es la señal de que **se está hablando con HBase**. En esta sección, los bloques que empiezan con `hbase:001:0>` (o que tienen comandos como `create`, `put`, `scan`) **se escriben ahí**, no en la terminal ni en Python. Para salir: `exit`.

Dos cosas de la sintaxis, porque desconciertan al principio:

- Los **nombres** (de tabla, de familia, de fila) van entre **comillas simples**: `'demo'`, `'m'`.
- Las **opciones** van entre llaves, con `=>` entre el nombre y el valor: `{NAME => 'm', VERSIONS => 3}`. (La consola de HBase está construida sobre Ruby, de ahí la sintaxis.)

Los tiempos y los *timestamps* que aparecen en las respuestas de los ejemplos de este documento son ilustrativos: en su pantalla serán otros.

### 4.4 Desde Python: `happybase`

En el notebook, la primera conexión es:

```python
import happybase
conn = happybase.Connection("127.0.0.1", 9090)    # el puerto 9090 es el de Thrift
print(conn.tables())                               # lista las tablas existentes
```

- `happybase.Connection("127.0.0.1", 9090)` abre la conexión con el servidor Thrift del contenedor (`127.0.0.1` es "esta misma máquina"; el contenedor publica su puerto 9090 hacia afuera).
- `conn` es **la conexión**: todo lo que sigue es `conn.<algo>` o `tabla.<algo>`.
- `conn.tables()` devuelve la lista de tablas. La primera vez: `[]`.

La traducción entre la consola y Python es casi directa:

| Qué se quiere | En `hbase shell` | En `happybase` (Python) |
|---|---|---|
| Crear una tabla | `create 'demo', {NAME => 'm', VERSIONS => 3}, 'meta'` | `conn.create_table("demo", {"m": dict(max_versions=3), "meta": dict()})` |
| Guardar un dato | `put 'demo', 'fila1', 'm:valor', '42.5'` | `demo.put(b"fila1", {b"m:valor": b"42.5"})` |
| Leer una fila | `get 'demo', 'fila1'` | `demo.row(b"fila1")` |
| Recorrer filas | `scan 'demo'` | `demo.scan()` |
| Listar tablas | `list` | `conn.tables()` |
| Borrar una tabla | `disable 'demo'` y luego `drop 'demo'` | `conn.delete_table("demo", disable=True)` |

(Donde `demo = conn.table("demo")` es el objeto que representa a esa tabla.)

**Todo son bytes.** Fíjense en las `b` delante de las comillas en Python (`b"fila1"`, `b"m:valor"`). HBase no sabe de números, fechas ni textos: **guarda secuencias de bytes**, y lo que significan lo decide quien las lee. Por eso en Python hay que convertir: `str(42.5).encode()` para guardar y `float(valor)` o `valor.decode()` para leer. Esto parece un detalle y es una de las lecciones centrales del laboratorio (ver el ejercicio 2.4 en la sección 6).

### 4.5 Lo que `happybase` no puede hacer: el ayudante `hbase_shell()`

Algunas operaciones no existen en `happybase`: crear una tabla ya **dividida en regiones** (`SPLITS`), forzar un `flush` o una `major_compact`. Para esas, el notebook trae una función auxiliar, `hbase_shell(...)`, que recibe un texto con comandos de la consola, los ejecuta dentro del contenedor (con `docker compose exec`) y devuelve la respuesta. En otras palabras: es "escribir en `hbase shell`" pero desde una celda del notebook. Las celdas que la usan están dadas; ustedes solo tienen que leer qué comando se manda.

## 5. El modelo de datos: un mapa ordenado de bytes

### 5.1 La idea de fondo

Si vienen de las bases relacionales, olviden las tablas con columnas fijas. La imagen correcta es esta:

> Cada **celda** de HBase se identifica con tres cosas: **(row key, familia:columna, timestamp)**, y guarda un valor en **bytes**.

Y las filas están **ordenadas por row key**. Si lo imaginan en Python, es un diccionario de diccionarios, ordenado por la clave de afuera:

```python
{
  "CC-001#2026-10-09T08:15:00.000-03:00": {          # ← row key
      "m:valor":       {1790000000000: b"42.5"},      # ← columna → {timestamp: valor}
      "m:tipo":        {1790000000000: b"flujo_vehicular"},
      "meta:comuna":   {1790000000000: "Concepción".encode()},
  },
  "CC-001#2026-10-09T08:16:00.000-03:00": { ... },
}
```

### 5.2 Las piezas, una por una

- **Tabla:** el contenedor de todo, como en una base relacional. En el laboratorio habrá `demo` (para jugar), `lecturas`, `lecturas_ts` y `lecturas_inv`.
- **Fila y *row key* (clave de fila):** cada fila se identifica con una clave única, escrita en bytes. **Es lo más importante de HBase**: define el orden de las filas, dónde viven y qué preguntas son rápidas. Sin una row key no hay fila. (Es como el *primary key*, pero con un rol mucho más grande: es el único índice.)
- **Familia de columnas (*column family*):** un grupo de columnas que se guardan juntas en disco. **Se declara al crear la tabla** y casi no cambia después. En el laboratorio: `m` (medición) y `meta` (datos descriptivos). Se usan pocas, a propósito: cada familia se guarda en archivos separados.
- **Columna (*qualifier*):** el nombre de un dato dentro de una familia. Se escribe `familia:columna`, por ejemplo `m:valor`. **Las columnas no se declaran**: aparecen cuando se escribe en ellas, y cada fila puede tener las suyas.
- **Celda:** lo que hay en el cruce de una fila y una `familia:columna`. Guarda un valor y su *timestamp*.
- **Timestamp y versiones:** cada vez que se escribe una celda, HBase **no sobrescribe**: agrega una **versión nueva** con su timestamp (por defecto, la hora de la escritura, en milisegundos desde 1970). Cada familia define cuántas versiones recuerda. Al leer sin pedir nada más, se obtiene la más reciente.
- **Disperso (*sparse*):** una celda sin dato **no ocupa nada**. Una fila puede tener 3 columnas y la siguiente 300, sin que haya "NULL" guardados.

Una fila de ejemplo, como la verían en una tabla:

| row key | familia:columna | timestamp | valor |
|---|---|---|---|
| `CC-001#2026-10-09T08:15:00.000-03:00` | `m:valor` | 1790…081 | `42.5` |
| `CC-001#2026-10-09T08:15:00.000-03:00` | `m:tipo` | 1790…081 | `flujo_vehicular` |
| `CC-001#2026-10-09T08:15:00.000-03:00` | `meta:comuna` | 1790…081 | `Concepción` |

(Una "fila" en HBase es el conjunto de celdas que comparten row key; en la tabla de arriba son tres celdas de una misma fila.)

### 5.3 Crear una tabla

En `hbase shell`:

```
create 'demo', {NAME => 'm', VERSIONS => 3}, 'meta'
```

Palabra por palabra:

- `create` — el comando.
- `'demo'` — el nombre de la tabla.
- `{NAME => 'm', VERSIONS => 3}` — la primera familia de columnas: se llama `m` y recuerda hasta **3 versiones** de cada celda.
- `'meta'` — la segunda familia, con las opciones por defecto (que en HBase 2 recuerdan solo **1** versión).

En Python, lo mismo:

```python
conn.create_table("demo", {"m": dict(max_versions=3), "meta": dict()})
demo = conn.table("demo")
print(conn.tables())      # → [b'demo']
```

- El segundo argumento es un diccionario `familia → opciones`. `dict()` vacío significa "opciones por defecto".
- `conn.table("demo")` entrega el objeto con el que se trabaja sobre esa tabla.
- `conn.tables()` devuelve `[b'demo']`: de nuevo, bytes.

### 5.4 Guardar y leer: `put` y `get`

En `hbase shell`:

```
put 'demo', 'CC-001#2026-10-09T08:15:00.000-03:00', 'm:valor', '42.5'
get 'demo', 'CC-001#2026-10-09T08:15:00.000-03:00'
```

- `put <tabla>, <row key>, <familia:columna>, <valor>` — guarda **una celda**. Para guardar varias columnas de la misma fila hay que repetir el `put` (en `happybase`, un solo `put` acepta varias).
- `get <tabla>, <row key>` — devuelve todas las celdas de esa fila (las versiones más recientes). La respuesta tiene la forma:

```
COLUMN                CELL
 m:valor              timestamp=1790000000000, value=42.5
```

En Python:

```python
fila = b"CC-001#2026-10-09T08:15:00.000-03:00"
demo.put(fila, {b"m:valor": b"42.5", b"m:tipo": b"flujo_vehicular",
                b"meta:comuna": "Concepción".encode()})
demo.row(fila)
```

- El primer argumento de `put` es la row key; el segundo es un diccionario `columna → valor`, todo en bytes.
- `"Concepción".encode()` convierte el texto a bytes en UTF-8; la "ó" ocupa dos bytes.
- `demo.row(fila)` devuelve un diccionario:

```python
{b'm:valor': b'42.5', b'm:tipo': b'flujo_vehicular', b'meta:comuna': b'Concepci\xc3\xb3n'}
```

Lo que aparece como `\xc3\xb3` es la "ó" en dos bytes. **HBase no sabe que `42.5` es un número ni que `Concepción` es texto**; eso lo decide quien lee.

### 5.5 Versiones: un `put` agrega, no pisa

Si escriben tres veces la misma celda:

```python
demo.put(fila, {b"m:valor": b"43.0"})
demo.put(fila, {b"m:valor": b"44.1"})
demo.row(fila)[b"m:valor"]                                          # → b'44.1'
demo.cells(fila, b"m:valor", versions=3, include_timestamp=True)    # → [(b'44.1', ts3), (b'43.0', ts2), (b'42.5', ts1)]
```

- `row()` devuelve solo la versión **más reciente**.
- `cells(fila, columna, versions=3, include_timestamp=True)` devuelve **todas las que recuerda** (hasta 3), de la más nueva a la más vieja, cada una con su timestamp.
- Si escribieran una **cuarta** vez, la familia `m` solo recuerda 3: las lecturas devolverían las 3 más recientes y la más antigua desaparecería (físicamente se descarta en la *compaction*, sección 8).

En la consola, el equivalente de `cells(...)` es `get 'demo', '<row key>', {COLUMN => 'm:valor', VERSIONS => 3}`.

Esto es lo que más sorprende desde el mundo relacional: **no existe "actualizar" en el sentido de pisar un dato**. Actualizar es escribir de nuevo. Y es lo que permite que un evento repetido no cree filas duplicadas (ver 6.4).

### 5.6 Filas dispersas y orden: `scan`

```python
demo.put(b"TAL-003#2026-10-09T08:15:00.500-03:00", {b"m:valor": b"61.2", b"m:pm10": b"88"})
for k, v in demo.scan():
    print(k, v)
```

- Esta segunda fila tiene una columna (`m:pm10`) que la primera no tiene. **No hay que declararla en ningún lado**: por eso se dice que HBase es *disperso*. La tabla `demo` no "tiene" un número fijo de columnas: cada fila tiene las suyas.
- `demo.scan()` recorre la tabla **en orden de row key**. La fila de `CC-001#…` sale antes que la de `TAL-003#…` porque "C" va antes que "T". (En 6.1 se ve por qué este orden importa tanto.)

En la consola: `scan 'demo'`.

### 5.7 Borrar

- `delete 'demo', '<row key>', 'm:valor'` borra una celda; `deleteall 'demo', '<row key>'`, una fila completa.
- **Un `delete` no borra el dato del disco**: escribe una **lápida** (*tombstone*), una marca que dice "ignorar lo anterior". Los datos reales se eliminan después, en una *compaction mayor* (sección 8).
- Una tabla no se puede borrar mientras está activa: primero `disable 'demo'` y luego `drop 'demo'`. En Python, `conn.delete_table("demo", disable=True)` hace las dos cosas. Lo verán al principio de la celda del ejercicio 1.1: borra la tabla `demo` si existe, para poder re-ejecutar el notebook.

## 6. La row key es el índice

### 6.1 Las filas están ordenadas… como texto

HBase mantiene las filas ordenadas por row key, comparando los **bytes uno a uno**, de izquierda a derecha (orden *lexicográfico*, como un diccionario). Esto tiene consecuencias que conviene tener muy presentes:

- Las claves `"1"`, `"2"`, `"10"` se ordenan `"1"`, `"10"`, `"2"` (porque `"1"` va antes que `"2"`, y el segundo carácter de `"10"` ya no se compara con nada). Para que los números ordenen como números, se **rellenan con ceros a un ancho fijo**: `"001"`, `"002"`, `"010"`.
- Las fechas en formato ISO 8601 (`2026-10-09T08:15:00.000-03:00`) se ordenan bien como texto **siempre que todas tengan el mismo formato y el mismo ancho, y la misma zona horaria**. Por eso en el laboratorio se pasan todas a hora de Chile (UTC−3).

### 6.2 Dos formas rápidas de leer: `get` y `scan` por rango

- **`get` por row key exacta:** HBase sabe en qué región está esa clave y va directo. Rápido.
- **`scan` por rango de row keys:** como las filas están contiguas y ordenadas, un rango se lee de corrido, sin saltos. También rápido, y su costo depende del tamaño del rango, no del tamaño de la tabla.

En el laboratorio, la tabla `lecturas` usa como row key `estacion#timestamp` (por ejemplo, `CC-001#2026-10-08T09:30:00.000-03:00`). Entonces la pregunta "las lecturas de CC-001 entre las 09:00 y las 10:00 del 8 de octubre" es **un tramo contiguo**:

```python
hora_cc = list(conn.table("lecturas").scan(
    row_start=b"CC-001#2026-10-08T09:00",
    row_stop=b"CC-001#2026-10-08T10:00"))
```

- `row_start` es el punto desde donde se empieza a leer (**incluido**).
- `row_stop` es el punto donde se termina (**excluido**).
- Como las claves empiezan con la estación, todo CC-001 está junto; y dentro de ella, por hora.
- El equivalente en la consola: `scan 'lecturas', {STARTROW => 'CC-001#2026-10-08T09:00', STOPROW => 'CC-001#2026-10-08T10:00'}`.

**Medido:** 442 lecturas en ~0,01 segundos, en una tabla de más de un millón de filas. Un `scan` con `row_prefix=b"CC-001#"` hace lo mismo para "todo lo que empiece con esto".

### 6.3 Lo que la row key NO hace rápido: filtrar por valor

Ahora la pregunta "todas las lecturas con valor mayor que 100". El **valor** no está en la row key. HBase no tiene índices secundarios (no puede "mirar el índice de `valor`" como lo haría PostgreSQL con un índice sobre esa columna). Para responder tiene que **recorrer la tabla entera** y evaluar cada celda:

```python
conn.table("lecturas").scan(
    filter="SingleColumnValueFilter('m', 'valor', >, 'binary:100', true, true)")
```

- Un **filtro** es una condición que HBase evalúa *en el servidor*, para no mandar al cliente las filas que no pasan. Pero **igual tiene que leerlas todas**.
- `SingleColumnValueFilter('m', 'valor', >, 'binary:100', true, true)` se lee: "de la columna `m:valor`, quiero las celdas cuyo valor sea mayor que `100`, comparando como `binary` (bytes); `true, true` son dos opciones: omitir las filas que no tengan esa columna, y mirar solo la versión más reciente".

**Medido:** el filtro recorrió ~1,19 millones de filas en ~7 segundos, unas **mil veces más lento** que el `scan` por rango. Y la diferencia **crece con la tabla**: con cinco años de datos en vez de una semana, el rango seguiría tardando centésimas de segundo y el filtro, minutos u horas.

**Dos lecciones, en una sola celda del laboratorio:**

1. **Sin índices secundarios, una consulta que no usa la row key recorre todo.** La row key es *el* índice.
2. **El filtro compara bytes, no números.** Comparado como texto, `"5.2"` es **mayor** que `"100"` (porque `"5"` > `"1"`). Por eso el filtro "mayor que 100" devolvió **1.159.725 filas** cuando solo **76.605** valían de verdad más de 100. Es lo mismo de 6.1: lo que HBase guarda son bytes, y no sabe que eran números.

**¿Y si "los valores sobre un umbral" fuera una pregunta frecuente?** En HBase se **duplica a propósito**: se guarda lo mismo en **otra tabla** cuya row key responda esa pregunta (por ejemplo, empezando por el nivel de valor), y la aplicación escribe en las dos. Es lo que hace el laboratorio con `lecturas` y `lecturas_ts`: una misma semana de datos, dos diseños de row key, para dos preguntas distintas. Se paga con espacio y con trabajo extra al escribir; se gana velocidad al leer.

### 6.4 Contar filas, y eventos repetidos

En HBase no existe un `COUNT(*)` guardado en alguna parte: contar es **recorrer** la tabla. El notebook lo hace con dos filtros que hacen que viaje solo el mínimo (la primera clave de cada fila):

```python
sum(1 for _ in conn.table("lecturas").scan(filter="FirstKeyOnlyFilter() AND KeyOnlyFilter()"))
```

**Medido:** se escribieron **1.209.600** eventos (una semana a 2 por segundo) y al contar aparecen **1.185.587** filas: **24.013 `put` no crearon una fila nueva.** ¿Por qué? Porque el generador de eventos repite a propósito una pequeña fracción de ellos (lo vieron en el Lab 06, ejercicio 3.1). Un evento repetido tiene la **misma estación y el mismo timestamp**, es decir, **la misma row key**: el segundo `put` cae sobre la misma celda y simplemente agrega una versión. **La row key hizo la deduplicación.** Esta idea (escrituras *idempotentes*: repetirlas no cambia el resultado) vuelve en la sección 11.

## 7. Arquitectura: regiones y servidores

### 7.1 Regiones

Una tabla de HBase se corta en franjas contiguas de row keys. Cada franja se llama **región**. Si las claves van de la "A" a la "Z", una región podría ser `A–F`, otra `G–M` y otra `N–Z`.

- Cuando una región crece demasiado (del orden de **10 GB** en la configuración por defecto), HBase la **divide en dos** sola.
- En el laboratorio las tablas se crean **ya divididas** (*pre-split*), porque con una semana de datos nunca llegarían al tamaño de división y quedarían en una sola región, sin nada que ver:

```
create 'lecturas',    'm', SPLITS => ['COR', 'PEN', 'TAL']
create 'lecturas_ts', 'm', SPLITS => ['2026-10-04', '2026-10-06', '2026-10-08']
```

- `SPLITS => [...]` lista los puntos de corte. Cuatro regiones por tabla: en `lecturas`, `'' → COR`, `COR → PEN`, `PEN → TAL` y `TAL → ''` (donde `''` significa "desde el principio" o "hasta el final"). Como la row key de `lecturas` empieza con la estación, el corte reparte las estaciones: las que empiezan con "CC" en la primera, "COR" y "HUA" en la segunda, "PEN" y "SPP" en la tercera, "TAL" en la última. En `lecturas_ts` los cortes son por fecha, porque su row key empieza con el timestamp.
- Esta orden va por `hbase_shell()` (sección 4.5), porque `happybase` no sabe hacerla.

### 7.2 Quién es quién

- **RegionServer:** el proceso que atiende las lecturas y escrituras de las regiones que tiene asignadas. En un cluster hay muchos, en máquinas distintas.
- **HMaster:** el coordinador. Crea tablas, asigna regiones a los RegionServers y las reasigna si uno se cae. No atiende lecturas ni escrituras de datos.
- **ZooKeeper:** un servicio de coordinación que sabe **quién está vivo** y dónde está cada pieza clave.
- **HDFS:** donde finalmente se guardan los archivos, replicados entre máquinas (en el laboratorio, una carpeta local).
- **`hbase:meta`:** una tabla especial de HBase que guarda **qué región está en qué servidor**.

### 7.3 Cómo encuentra el cliente un dato

Cuando un cliente quiere leer o escribir una row key, **no pasa por el HMaster**. Pregunta (vía ZooKeeper y `hbase:meta`) en qué región está esa clave y en qué RegionServer, guarda la respuesta, y a partir de ahí **habla directo con ese RegionServer**. Por eso HBase escala: el coordinador no es un cuello de botella.

> **Escalar = agregar RegionServers. Las regiones se reparten solas.**

### 7.4 En el laboratorio

Todo es un único proceso y las cuatro regiones de cada tabla las sirve el mismo "servidor" (`pmd-hbase`). Se puede verlo en <http://localhost:16010>, entrando a una tabla: verán sus regiones, con la clave de inicio y de fin de cada una. El código también las lista: `conn.table("lecturas").regions()`.

## 8. Por qué escribe tan rápido: el camino de escritura (LSM)

### 8.1 La idea

HBase evita lo que dejaba mal parada a la base relacional: **nunca modifica un archivo en su lugar.** Cada escritura es un "agregar al final" (secuencial, rápido) más un "ordenar en memoria". Esta técnica se llama *Log-Structured Merge tree* (**LSM**).

### 8.2 Los pasos

```
put  →  WAL (log en disco)  →  MemStore (RAM, ordenada)  →  flush  →  HFile (archivo ordenado, inmutable)  →  compaction (fusiona HFiles)
```

1. **WAL (*write-ahead log*):** primero, la escritura se anota al final de un archivo de registro. Es solo agregar al final. Si el servidor se cae, este registro permite reconstruir lo que no alcanzó a llegar a disco.
2. **MemStore:** además, la escritura entra a una estructura en RAM, **ordenada por row key**. Hay una por familia de columnas de cada región. Aquí es donde "ahora mismo" viven los datos recientes.
3. **Flush:** cuando la MemStore se llena (por defecto, 128 MB), se **vuelca a disco** como un archivo nuevo.
4. **HFile:** el archivo resultante: **ordenado por row key** e **inmutable** (nunca se modifica). Una región acumula varios con el tiempo.
5. **Compaction:** HBase fusiona HFiles en segundo plano. La *menor* junta algunos archivos pequeños; la *mayor* junta todos los de una región en uno solo, y en ese momento **descarta las versiones sobrantes y las celdas cubiertas por lápidas** (sección 5.7).

> Fíjense que el WAL es un log de solo-agregar, como el stream de Redis: la misma idea, ahora al servicio de la durabilidad.

### 8.3 ¿Y leer?

Una lectura tiene que mirar **la MemStore y todas las HFiles** de la región, y combinar lo que encuentre (quedándose con lo más reciente). Por eso demasiadas HFiles hacen más lentas las lecturas, y por eso existe la compaction: es el precio de escribir rápido.

### 8.4 Lo que ven en el laboratorio (Parte 4)

El notebook mira el disco del contenedor y cuenta las HFiles de cada región de `lecturas`:

- **Antes de cualquier `flush`:** algunas regiones tienen **0** HFiles. ¿Dónde están entonces sus filas? En la **MemStore** y en el **WAL**. Medido: `0 · 0 · 0 · 1` HFiles por región (el patrón exacto puede variar), y un WAL de ~430 MB.
- **Después de `flush 'lecturas'`:** cada región tiene al menos una. Si escriben de nuevo (mismas keys: son versiones nuevas) y vuelven a hacer `flush`, **aparece una HFile más por región; las anteriores no cambian.** Medido: `1·1·1·2` y luego `2·2·2·3`.
- **Después de `major_compact 'lecturas'`:** una sola por región: `1·1·1·1`.

La imagen del laboratorio está configurada para que la compaction mayor deje liberar los archivos viejos a los 10 segundos (en HBase de fábrica son 2 minutos), para que el efecto se vea sin esperar.

**Apagar y prender (ejercicio 4.4).** Al reiniciar el contenedor, el número de filas es el mismo (medido: 1.192.643 antes y después). Al apagarse ordenadamente, HBase vacía la MemStore a disco; si se hubiera caído de golpe, lo recuperaría del WAL. Contrasten con el Lab 06: `docker compose down` del Redis de rescate lo borraba todo.

**Dos honestidades sobre el laboratorio.** (1) En un cluster, el WAL y los HFiles viven en HDFS, replicados ×3; aquí viven en el disco local del contenedor y la configuración desactiva una verificación de seguridad del WAL (`hbase.unsafe.stream.capability.enforce`), porque un disco local no garantiza lo mismo que HDFS. Es aceptable para aprender; no lo sería en producción. (2) Con HFiles tan chicas y un solo servidor, los efectos de rendimiento se ven, pero a escala de un PC.

## 9. Diseñar la row key es diseñar la base de datos

### 9.1 El problema: *hotspotting*

Si una tabla se reparte en regiones y cada región la atiende un servidor, ¿qué pasa si **todas las escrituras caen en la misma región**? Trabaja un solo servidor y los demás miran. Se llama ***hotspotting*** (punto caliente), y no se arregla agregando servidores.

Eso ocurre con las claves **monótonas** (que siempre crecen), como un timestamp al comienzo de la row key: lo que llega "ahora" es siempre lo más nuevo, y lo más nuevo siempre cae en la **última región**.

### 9.2 Tres diseños, la misma semana de datos

| Row key | Qué pasa con las escrituras | Qué pregunta hace rápida |
|---|---|---|
| `timestamp#estacion` → `2026-10-09T08:15:00…#CC-001` (tabla `lecturas_ts`) | **Todas** caen en la última región (la de "ahora"): hotspot | "Todo lo que pasó entre las 8 y las 9" (de todas las estaciones) |
| `estacion#timestamp` → `CC-001#2026-10-09T08:15:00…` (tabla `lecturas`) | Se reparten entre estaciones, es decir, entre regiones | "CC-001 entre las 8 y las 9": un solo `scan` contiguo |
| `estacion#(10¹³ − milisegundos)` (tabla `lecturas_inv`) | Se reparten igual | "La **última** lectura de CC-001": está primera |

**Medido (Parte 3, ejercicio 3.2).** El notebook escribe una hora "en vivo" (unos 7.000 eventos) en las dos primeras tablas y le pregunta a HBase cuántas escrituras recibió **cada región** (HBase lleva esa cuenta; el notebook la lee de sus métricas, las mismas que muestra la interfaz web):

```
lecturas    {'(inicio)': 2628, 'COR': 1749, 'PEN': 1362, 'TAL': 1318}
lecturas_ts {'(inicio)': 0,    '2026-10-04': 0, '2026-10-06': 0, '2026-10-08': 7057}
```

En `lecturas`, el trabajo se reparte (no parejo, porque las regiones no tienen la misma cantidad de estaciones, pero se reparte). En `lecturas_ts`, **las 7.057 escrituras caen en la última región y las demás no reciben ninguna.** Con cuatro servidores, uno trabajaría y tres estarían ociosos; con cuarenta, uno y treinta y nueve.

### 9.3 Técnicas para repartir y para leer lo más reciente

- **Poner primero algo que reparta**, como aquí la estación (se llama a veces *prefijo de dominio*).
- **Salting:** anteponer un prefijo calculado, como `hash(clave) % N`, que reparte claves monótonas en N regiones. Se paga leyendo N rangos en vez de uno al consultar.
- **Timestamp invertido:** si la pregunta típica es "lo más reciente", se guarda `10¹³ − milisegundos` en vez de los milisegundos. Como los milisegundos desde 1970 tienen 13 dígitos (hasta el año 2286), `10¹³ − ms` da siempre un número positivo de 13 dígitos que **decrece con el tiempo**, de modo que la lectura más nueva tiene la clave *más chica* y sale **primera** en un `scan`. Hay que rellenar con ceros a 13 dígitos (`:013d`) para que el orden como texto sea el orden numérico (6.1). Con eso, "la última lectura de cada estación" es un `scan(row_prefix=b"CC-001#", limit=1)`. **Medido:** las 16 estaciones en ~0,07 segundos.

### 9.4 Cómo se diseña una row key

1. **Escriban primero las preguntas** que la base va a responder, y cuál es la más frecuente o más importante.
2. **El comienzo de la row key es lo que se puede filtrar rápido.** Lo que van a pedir por igualdad o por rango debe ir primero, en el orden en que se pregunta.
3. **Eviten un comienzo monótono** (fechas, contadores) si hay escritura continua: hotspot.
4. **Ancho fijo y mismo formato** para lo que debe ordenar bien (ceros a la izquierda, ISO 8601, misma zona horaria).
5. **Que sea corta.** HBase repite la row key con **cada celda** en el disco; una clave larga multiplica el espacio.
6. **Si hay dos preguntas incompatibles, dos tablas.** La duplicación es normal en HBase.

> En PostGIS se diseñaba el índice. En HBase, **la row key ES el índice**, y se diseña según la pregunta.

## 10. Lo que HBase no hace, y cuándo no usarlo

- **No hay SQL ni *joins*.** Se puede agregar una capa SQL encima (Apache Phoenix), pero no viene de fábrica.
- **No hay índices secundarios.** Solo la row key (6.3).
- **Atomicidad solo por fila.** Escribir varias columnas de **una** fila es todo-o-nada; escribir varias **filas** no lo es.
- **Consistencia fuerte por fila.** Una lectura ve la última escritura confirmada de esa fila (a diferencia de otras bases NoSQL que priorizan la disponibilidad).
- **No sirve con pocos datos.** HBase tiene sentido cuando hay muchas máquinas y muchos datos; con datos que caben cómodamente en un PostgreSQL, ese PostgreSQL es la mejor opción.
- **No sirve para consultas analíticas arbitrarias** ("el promedio de flujo por comuna y hora del último mes") ni para consultas que no se conocen de antemano: esas piden una base analítica.
- **Pide diseñar con la pregunta en mano.** Un mal diseño de row key no se arregla con más máquinas.

## 11. Redis, HBase y PostGIS: cada uno en su lugar

| | **Redis** | **HBase** | **PostGIS** |
|---|---|---|---|
| Dónde vive | RAM | disco distribuido (HDFS) | disco, una máquina |
| Escala hasta | lo que cabe en la RAM | miles de millones de filas | lo que cabe en un servidor |
| Lee bien | clave exacta; últimas entradas | clave exacta; **rango** de claves | consultas complejas y geometría |
| En nuestro caso | las **últimas 7 horas** | los **últimos 5 años** | el **catastro**: estaciones, comunas, paraderos |

La pregunta, entonces, no es cuál es mejor, sino: **¿necesito los últimos segundos, la historia completa, o la geometría?** Un sistema real (y el proyecto semestral) puede usar los tres: PostGIS para el catastro de estaciones, Redis para lo que está pasando ahora, y HBase para guardar la historia.

### 11.1 El puente: del stream a HBase (Parte 5)

El laboratorio cierra uniendo las dos mitades del bloque. Un consumidor lee el stream compartido de Redis con **su propio consumer group** (`ingesta-<EQUIPO>`), guarda cada lote en la tabla `lecturas` y **recién después** confirma con `XACK`:

```
XREADGROUP  →  put en HBase  →  XACK
```

¿Por qué en ese orden? Piensen qué pasa si algo falla:

- **Si se cae antes del `put`:** la entrada queda *pendiente* en el grupo (nadie la confirmó) y otro consumidor puede rescatarla con `XCLAIM` (Lab 06, 3.4). **No se pierde nada.**
- **Si se cae justo entre el `put` y el `XACK`:** la entrada se entregará de nuevo y se volverá a escribir. Pero la row key es **la misma** (estación + timestamp), así que el segundo `put` solo agrega una versión a la misma celda. **No se duplica nada.**

Eso es lo que se llama *al menos una vez + escritura idempotente = cada evento guardado exactamente una vez, a efectos prácticos*. Dos detalles del código: los timestamps del VPS vienen en UTC y se **convierten a hora de Chile** para que las row keys calcen con las de la semana de histórico; y el `EQUIPO` de cada persona tiene que ser **único**, porque da nombre al grupo: dos personas con el mismo `EQUIPO` compartirían el grupo y se repartirían los eventos.

Esta Parte 5 es opcional y depende de que el servidor compartido esté disponible: si no conecta, el notebook lo avisa y se puede saltar sin perder el resto.

## 12. Guía práctica del Laboratorio 07

**Qué necesitan:** Docker con `docker compose` y **~4 GB de RAM asignados a Docker** (en Docker Desktop: Settings → Resources), ~3 GB de disco, Python con las dependencias de `requirements.txt` en un ambiente virtual, y la carpeta `Laboratorios/06/` al lado (el notebook importa `generador.py` de ahí). El `README.md` de la carpeta tiene los pasos de instalación.

**Tiempo:** 2 a 3 horas leyendo y completando; las cargas de datos son unos 3 minutos en un Mac reciente, y de 2 a 3 veces más en un PC más lento.

**Problemas frecuentes**

- **`docker compose build` es lento o falla.** Es la única parte que necesita internet de verdad (~340 MB). Reintenten; o pídanle a un compañero que ya la construyó: `docker save pmd-hbase | gzip > pmd-hbase.tar.gz` y, en su máquina, `docker load < pmd-hbase.tar.gz`.
- **HBase se cae o responde muy lento.** Casi siempre es memoria: aumenten la RAM asignada a Docker a 4 GB.
- **`happybase` no conecta (error de transporte o conexión rechazada).** HBase puede estar todavía arrancando: `docker compose up -d --wait` espera, pero si abrieron el notebook antes, vuelvan a ejecutar la celda de conexión. Revisen que el puerto 9090 no lo use otro programa.
- **Después de reiniciar el contenedor nada responde.** La conexión anterior murió con él: hay que crear `conn` de nuevo (el notebook lo hace en el ejercicio 4.4).
- **`ERROR: Table already exists`.** No es un problema: significa que re-ejecutaron una celda de creación.
- **El filtro del ejercicio 2.4 tarda muchísimo.** Es lo esperado: esa es la lección.
- **Empezar de cero.** `docker compose down -v` borra el contenedor y los datos; después vuelven a la Parte 0. Las cargas son idempotentes (mismas keys, versiones nuevas), así que re-ejecutar una celda de carga no rompe nada.
- **Probado en:** Mac con Apple Silicon. La imagen base es multiarquitectura y debería funcionar igual en Windows y Linux, pero si algo falla en su máquina, avisen al canal para resolverlo.
- **Al terminar:** la última celda hace `docker compose down -v` y recupera ~1,5 GB.

## 13. Glosario

- **HBase:** base de datos NoSQL de tipo *wide-column*, distribuida, que guarda en disco; inspirada en Bigtable de Google.
- **HDFS:** sistema de archivos distribuido de Hadoop; parte los archivos en bloques y guarda copias en varias máquinas.
- **Standalone:** modo de HBase donde todo corre en un solo proceso en una máquina; el del laboratorio.
- **Tabla:** contenedor de filas.
- **Row key:** clave que identifica una fila, en bytes; define el orden, la ubicación y las consultas rápidas.
- **Familia de columnas (*column family*):** grupo de columnas que se guardan juntas; se declara al crear la tabla.
- **Columna (*qualifier*):** nombre de un dato dentro de una familia, `familia:columna`; no se declara.
- **Celda:** valor en el cruce de fila y `familia:columna`, con su timestamp.
- **Versión:** cada escritura de una celda agrega una versión con su timestamp; la familia define cuántas recuerda.
- **Disperso (*sparse*):** una celda sin dato no ocupa espacio.
- **Región:** rango contiguo de row keys de una tabla.
- **RegionServer:** proceso que atiende las regiones que tiene asignadas.
- **HMaster:** coordinador: crea tablas y asigna regiones.
- **ZooKeeper:** servicio de coordinación que sabe quién está vivo.
- **`hbase:meta`:** tabla de sistema que dice qué región vive en qué servidor.
- **Pre-split:** crear la tabla ya dividida en regiones.
- **WAL (*write-ahead log*):** registro donde se anota cada escritura antes de aplicarla; sirve para recuperarse de una caída.
- **MemStore:** buffer en RAM, ordenado, donde entran las escrituras recientes.
- **Flush:** volcar la MemStore a disco como un archivo nuevo.
- **HFile:** archivo en disco, ordenado e inmutable, con datos de una familia.
- **Compaction (menor / mayor):** fusión de HFiles; la mayor deja una por región y descarta versiones sobrantes y lápidas.
- **Tombstone (lápida):** marca que dice "ignorar lo anterior"; es lo que escribe un `delete`.
- **LSM (*log-structured merge*):** técnica de escribir siempre agregando y fusionar después.
- **Hotspotting:** que todas las escrituras caigan en una misma región.
- **Salting:** prefijo calculado que reparte claves monótonas entre regiones.
- **Thrift:** servidor intermedio por el que `happybase` habla con HBase (puerto 9090).
- **Idempotente:** una operación que, repetida, deja el mismo resultado que una sola vez.
- **Phoenix:** capa SQL opcional sobre HBase.

## 14. Autoevaluación

Intenten responder sin mirar; las respuestas breves están al final.

1. Con los números del stream del VPS (88 bytes por entrada, 2 eventos por segundo), ¿cuánta RAM haría falta para guardar 5 años de 16 sensores? ¿Por qué eso descarta a Redis para guardar la historia?
2. ¿Qué dos cosas de PostgreSQL (B-trees y una sola máquina) hacen difícil sostener escrituras masivas durante años?
3. ¿Qué identifica una celda en HBase? ¿Qué significa que "todo son bytes"?
4. ¿Qué pasa si escriben tres veces la misma celda? ¿Qué devuelven `row()` y `cells()`?
5. Si no declaré la columna `m:pm10` al crear la tabla, ¿puedo guardar en ella? ¿Qué pasa con las filas que no la tienen?
6. ¿Por qué `scan` con `row_start`/`row_stop` es tan rápido y un filtro por valor tan lento? ¿Cuál de los dos crece con el tamaño de la tabla?
7. ¿Por qué el filtro "valor > 100" devolvió casi todas las filas si muy pocas superan 100?
8. Si "los valores sobre un umbral" fuera una pregunta frecuente, ¿qué harían?
9. ¿Qué es una región? ¿Quién decide qué servidor la atiende, y quién atiende las lecturas?
10. Describan el camino de un `put`: WAL, MemStore, flush, HFile. ¿Por qué nunca se modifica un archivo en su lugar?
11. ¿Para qué sirve la compaction mayor? ¿Por qué un `delete` no libera espacio de inmediato?
12. ¿Qué es el *hotspotting*? ¿Se arregla agregando servidores? ¿Por qué una row key que empieza con el timestamp lo produce?
13. ¿Por qué se usa `10¹³ − milisegundos` y se rellena a 13 dígitos?
14. En el puente stream → HBase, ¿por qué el `XACK` va después del `put`? ¿Qué pasa si un evento se guarda dos veces?
15. Para su proyecto semestral: ¿qué row key usarían y qué pregunta harían rápida? ¿Qué dato iría en Redis y cuál en HBase?

**Respuestas breves**

1. 2 × 86.400 × 365 × 5 ≈ 315 millones de entradas × 88 bytes ≈ 28 GB, solo con 16 sensores. La historia crece sin tope, y Redis la tiene toda en RAM.
2. Los B-trees se modifican en su lugar (escritura aleatoria sostenida) y todo vive en una máquina con techo de disco y CPU; crecer exige rediseñar.
3. (row key, familia:columna, timestamp). HBase no sabe de tipos: guarda secuencias de bytes y quien lee decide qué significan.
4. Se agregan versiones, no se pisa. `row()` devuelve la más reciente (44.1); `cells(…, versions=3)` devuelve las tres, con timestamp. Una cuarta desplaza a la más antigua.
5. Sí: las columnas no se declaran; solo las familias. Las filas sin esa columna simplemente no tienen celda (no ocupa espacio).
6. El rango lee un tramo contiguo ya ordenado; el filtro lee toda la tabla. El filtro crece con la tabla; el rango, con el tamaño del tramo.
7. Compara bytes, no números: `"5.2"` > `"100"` porque `"5"` > `"1"`. Las celdas guardan texto.
8. Duplicar: otra tabla cuya row key responda esa pregunta, escrita en paralelo por la aplicación.
9. Un rango contiguo de row keys. El HMaster asigna; el RegionServer asignado atiende; el cliente habla directo con él.
10. Se anota en el WAL, se ordena en la MemStore, al llenarse se vuelca como HFile inmutable, y la compaction los fusiona. Así toda escritura es secuencial.
11. Fusiona todas las HFiles de una región y descarta versiones sobrantes y lápidas. Un `delete` solo escribe una lápida; el dato se elimina físicamente en esa compaction.
12. Que todas las escrituras caigan en una región. No se arregla con más servidores: los nuevos no reciben tráfico. Con el timestamp al comienzo, lo nuevo siempre cae en la última región.
13. Para que lo más reciente tenga la clave más chica y salga primero; 13 dígitos fijos para que el orden como texto sea el numérico.
14. Si se cae antes del `put`, la entrada queda pendiente y se rescata; si se cae entre el `put` y el `XACK`, se reescribe con la misma row key: solo agrega una versión. Cada evento queda una vez.
15. Respuesta personal: debe partir por las preguntas del proyecto, poner primero lo que se filtra por igualdad o rango, evitar un comienzo monótono, y distinguir "ahora" (Redis) de "historia" (HBase).

## 15. Referencias

- Documentación oficial de Apache HBase (*The Apache HBase Reference Guide*): <https://hbase.apache.org/book.html>
- Chang, F. y otros (2006). *Bigtable: A Distributed Storage System for Structured Data*. OSDI '06, Google.
- Documentación de `happybase`: <https://happybase.readthedocs.io/en/latest/>
- Texto guía del curso: Bahga, A. & Madisetti, V. (2016). *Big Data Science & Analytics: A Hands-On Approach*, VPT.
