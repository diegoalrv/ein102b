# Contenidos — Neo4j I: consultar directo al contenedor

**Curso:** Procesamiento Masivo de Datos (ELE051-B / EIN102B) · Paralelo 701 · 2026-2
**Bloque Grafos (1 de 2) · Material para trabajar en casa · octubre de 2026**

> Material de estudio del Laboratorio 08. Explica cómo hablarle a Neo4j **sin pasar por Python**: con la consola `cypher-shell`, que vive dentro del contenedor, y con el Neo4j Browser. Sirve para probar una consulta rápido, para cargar el grafo a mano y como ruta alternativa si el driver de Python no funciona en su máquina. Todas las respuestas que aparecen aquí salieron de una corrida contra el contenedor del laboratorio, con el grafo recién cargado.

---

## 1. Tres puertas a la misma base

Neo4j es **un servicio**: un programa que corre dentro del contenedor `pmd-neo4j` y guarda el grafo en el volumen `pmd-neo4jdata`. Para usarlo hace falta un **cliente** que le mande consultas en Cypher. En el laboratorio hay tres:

| Cliente | Dónde se escribe | Por dónde llega a Neo4j |
|---|---|---|
| El notebook (`q("…")`) | una celda de Python | el driver `neo4j`, por Bolt (puerto 7687) |
| `cypher-shell` | la terminal, dentro del contenedor | Bolt, dentro del mismo contenedor |
| Neo4j Browser | el navegador, en <http://localhost:7474> | Bolt (puerto 7687), desde la página |

Las tres hablan con **la misma base**. Si crean una parada desde la consola, el notebook la ve en la consulta siguiente, y al revés. Lo único que cambia es cómo se escribe la consulta y cómo se ve la respuesta.

## 2. Levantar y cargar, desde la terminal

Todos estos comandos se escriben en la **terminal de su computador** (Terminal en Mac y Linux; PowerShell en Windows), **dentro de la carpeta `Laboratorios/08`**. No son Cypher ni Python.

```bash
docker compose up -d --wait
```

- Levanta el contenedor y **espera** a que Neo4j acepte consultas (30–60 s la primera vez). Es lo mismo que hace la Parte 0 del notebook.

```bash
docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo < 01_cargar_grafo.cypher
```

- Carga el grafo completo. Se hace **una sola vez** (ver la sección 5).

Para comprobar que quedó cargado:

```bash
docker exec pmd-neo4j cypher-shell -u neo4j -p pmd2026neo "MATCH (n) RETURN labels(n)[0] AS tipo, count(*) AS n ORDER BY tipo"
```

Respuesta esperada:

```
tipo, n
"Comuna", 7
"Linea", 4
"Parada", 12
```

## 3. La consola `cypher-shell`

### 3.1 Abrirla y cerrarla

```bash
docker compose exec neo4j cypher-shell -u neo4j -p pmd2026neo
```

- `docker compose exec` ejecuta un programa **dentro** de un contenedor que ya corre. `neo4j` es el nombre del servicio (como aparece en `docker-compose.yml`), y `cypher-shell` es el programa.
- `-u` y `-p` son el usuario y la clave.
- `docker exec -it pmd-neo4j cypher-shell -u neo4j -p pmd2026neo` hace lo mismo, pero nombra al **contenedor** en vez del servicio. Sirve desde cualquier carpeta.

Al entrar, la consola saluda así:

```
Connected to Neo4j using Bolt protocol version 5.8 at neo4j://localhost:7687 as user neo4j.
Type :help for a list of available commands or :exit to exit the shell.
Note that Cypher queries must end with a semicolon.
neo4j@neo4j>
```

`neo4j@neo4j>` es la señal de que **se está hablando con Neo4j**: usuario `neo4j`, base de datos `neo4j`. Para salir: `:exit`.

### 3.2 Escribir consultas: el punto y coma

En la consola, **cada consulta termina en `;`**. Sin él, Neo4j no la ejecuta: la consola asume que la consulta sigue en la línea siguiente y espera. Eso permite escribir en varias líneas:

```
neo4j@neo4j> MATCH (:Parada {id: 'P01'})-[r:SIGUE_A]-(v:Parada)
             RETURN v.nombre AS vecino, r.minutos AS minutos
             ORDER BY minutos;
+---------------------------------------+
| vecino                      | minutos |
+---------------------------------------+
| "Universidad de Concepción" | 6       |
| "Barrio Norte"              | 7       |
| "Puente Llacolén"           | 9       |
| "Mall del Trébol"           | 12      |
+---------------------------------------+

4 rows
ready to start consuming query after 1 ms, results consumed after another 1 ms
```

- La respuesta es una tabla. Los textos salen entre comillas dobles; los números, sin comillas.
- La última línea dice cuánto tardó Neo4j en preparar la respuesta y en entregarla.
- Las flechas ↑ y ↓ recorren las consultas anteriores. La tecla Tab completa los comandos que empiezan con `:`.

Si olvidan el `;`, la consola parece «colgada». No lo está: escriban `;` y Enter.

### 3.3 Los comandos que empiezan con dos puntos

Lo que empieza con `:` **no es Cypher**: son comandos de la consola. No llevan `;`.

| Comando | Qué hace |
|---|---|
| `:help` | lista todos los comandos |
| `:exit` | sale de la consola |
| `:param id => 'P01'` | define un parámetro `$id` para las consultas siguientes |
| `:begin` · `:commit` · `:rollback` | abre una transacción, la confirma o la deshace (sección 3.4) |
| `:history` | muestra las consultas anteriores |
| `:sysinfo` | información del servidor |

Un parámetro evita reescribir un valor en cada consulta:

```
neo4j@neo4j> :param id => 'P01'
neo4j@neo4j> MATCH (p:Parada {id: $id}) RETURN p.nombre;
+--------------+
| p.nombre     |
+--------------+
| "Plaza Perú" |
+--------------+
```

### 3.4 Probar sin miedo: `:begin` y `:rollback`

Normalmente, cada consulta se confirma sola apenas termina. Dentro de una **transacción** abierta con `:begin`, en cambio, los cambios quedan pendientes hasta `:commit` (se guardan) o `:rollback` (se deshacen). Sirve para probar una escritura sin ensuciar el grafo:

```
neo4j@neo4j> :begin
neo4j@neo4j# CREATE (n:Parada {id: 'P98', nombre: 'Prueba'});
neo4j@neo4j# MATCH (p:Parada) RETURN count(p) AS paradas;
+---------+
| paradas |
+---------+
| 13      |
+---------+
neo4j@neo4j# :rollback
neo4j@neo4j> MATCH (p:Parada) RETURN count(p) AS paradas;
+---------+
| paradas |
+---------+
| 12      |
+---------+
```

Dentro de la transacción la parada existe (13); después del `:rollback`, nunca existió (12). Mientras la transacción está abierta, el prompt termina en `#` en vez de `>`.

## 4. Una consulta suelta, sin entrar a la consola

Si la consulta va **al final del comando**, `cypher-shell` la ejecuta, imprime la respuesta y sale. No hace falta el `;`:

```bash
docker exec pmd-neo4j cypher-shell -u neo4j -p pmd2026neo "MATCH (p:Parada)-[:EN]->(:Comuna {nombre: 'Concepción'}) RETURN p.nombre ORDER BY p.nombre"
```

Cuidado con las comillas. La consulta completa va entre **comillas dobles** para la terminal, y los textos de Cypher van entre **comillas simples**: `'Concepción'`. Si las mezclan, la terminal corta la consulta donde no corresponde.

Con parámetros, la consulta va entre comillas **simples**, para que la terminal no confunda `$id` con una variable suya:

```bash
docker exec pmd-neo4j cypher-shell -u neo4j -p pmd2026neo --param "id => 'P07'" 'MATCH (p:Parada {id: $id}) RETURN p.nombre AS parada'
```

Respuesta: `"Terminal Talcahuano"`.

Cuando la salida va a la pantalla, sale como tabla; cuando va a un archivo o a otro programa, sale como texto separado por comas, más fácil de procesar. `--format plain` fuerza el texto y `--format verbose` fuerza la tabla:

```bash
docker exec pmd-neo4j cypher-shell -u neo4j -p pmd2026neo --format plain "SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties RETURN name, labelsOrTypes, properties" > restricciones.csv
```

`SHOW CONSTRAINTS` lista las restricciones de unicidad que creó el script: `parada_id`, `comuna_nombre` y `linea_id`.

## 5. Un archivo completo

```bash
docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo < 01_cargar_grafo.cypher
```

- `<` le entrega el **contenido** del archivo a la consola, como si lo escribieran ustedes. Por eso el archivo separa las consultas con `;`.
- `-i` («interactivo») deja que el archivo entre al contenedor. Sin `-i`, la consola no recibe nada.
- Cada sentencia se ejecuta en su propia transacción, en orden. Si una falla, la consola **se detiene ahí** y muestra el error.
- Con `docker compose exec`, en vez de `-i` se usa `-T`: `docker compose exec -T neo4j cypher-shell -u neo4j -p pmd2026neo < 01_cargar_grafo.cypher`.

En **PowerShell** (Windows), `<` no funciona. Usen:

```powershell
Get-Content 01_cargar_grafo.cypher | docker exec -i pmd-neo4j cypher-shell -u neo4j -p pmd2026neo
```

Si cargan el script **dos veces**, la segunda choca con la restricción de unicidad y se detiene en la primera comuna:

```
Node(0) already exists with label `Comuna` and property `nombre` = 'Concepción'
```

No pasa nada: el grafo sigue como estaba. Para empezar de cero, `MATCH (n) DETACH DELETE n;` y vuelvan a cargar.

## 6. El Neo4j Browser

<http://localhost:7474>, en el navegador. La primera vez pide la conexión: `bolt://localhost:7687`, usuario `neo4j`, clave `pmd2026neo`.

- Arriba hay una barra donde se escribe Cypher; Ctrl+Enter (Cmd+Enter en Mac) la ejecuta. El resultado aparece abajo, en un recuadro.
- Si la consulta devuelve nodos y relaciones (`RETURN p, r, q`), el Browser **los dibuja**. A la izquierda del recuadro se cambia entre la vista de grafo, la de tabla y la de texto.
- Al hacer clic en un nodo o en una flecha se ven sus propiedades.
- Si devuelve valores (`RETURN p.nombre`), los muestra como tabla.
- Se puede pegar un archivo completo, con varias sentencias separadas por `;`: el Browser las ejecuta en orden (puede preguntar antes si ejecutar todo).

## 7. Del notebook a la consola, y al revés

El Cypher es el mismo en las tres puertas. Lo que cambia es el envoltorio:

| En el notebook | En `cypher-shell` | En el Browser |
|---|---|---|
| `q("""MATCH … RETURN …""")` | `MATCH … RETURN …;` | `MATCH … RETURN …` |
| sin `;` | **con** `;` al final | `;` opcional |
| `q("… $id …", id="P01")` | `:param id => 'P01'` y luego `… $id …;` | `:param id => 'P01'` y luego `… $id …` |
| la respuesta es un `DataFrame` | la respuesta es una tabla de texto | la respuesta se dibuja |

Para pasar una celda del notebook a la consola: copien lo que está entre las triples comillas `"""` y agreguen `;` al final.

## 8. Problemas frecuentes

| Lo que ven | Qué pasa | Qué hacer |
|---|---|---|
| La consola no responde después de Enter | falta el `;` | escriban `;` y Enter |
| `The client is unauthorized due to authentication failure.` | clave equivocada, o un volumen viejo creado con otra clave | revisen la clave; si es el volumen, `docker compose down -v` y levanten de nuevo |
| `Invalid input 'RETURN': expected …` | error de sintaxis; el mensaje dice la línea y la columna | revisen paréntesis, llaves y comillas cerca de esa posición |
| Error de sintaxis raro en una consulta que «está bien» | comillas tipográficas (`'…'` curvas) copiadas desde un PDF | copien desde el notebook o el `.cypher`, o reescriban las comillas |
| `Connection refused` o `Unable to connect` | Neo4j todavía está arrancando, o el contenedor no corre | `docker compose ps`; si no dice `healthy`, esperen o `docker compose up -d --wait` |
| `Error response from daemon: No such container: pmd-neo4j` | el contenedor no está levantado | `docker compose up -d --wait` en `Laboratorios/08` |
