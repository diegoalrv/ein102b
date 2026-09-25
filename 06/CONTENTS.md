# Contenidos — Redis: datos en memoria y streaming

**Curso:** Procesamiento Masivo de Datos (ELE051-B / EIN102B) · Paralelo 701 · 2026-2
**Clase 7 · viernes 25 de septiembre de 2026 · Bloque Streaming + NoSQL (1 de 4)**

> Material de estudio, escrito para alguien que **nunca ha usado Redis**. Cada comando se explica antes de usarse — de dónde sale, qué hace cada palabra, y qué se espera ver como respuesta. Si algo acá no coincide con lo que vieron en clase, manda al canal del curso.

---

## 1. El problema: datos que no terminan de llegar

Todo lo visto en el bloque geoespacial (Clases 3 a 5) compartía un supuesto: los datos ya estaban ahí. Se cargaba un shapefile, un extracto de OpenStreetMap, un GTFS — un conjunto **cerrado**, con un tamaño conocido, sobre el que se hacían consultas. Ese supuesto es válido para un catastro de comunas o una red de paraderos, que cambian en escalas de meses. No es válido para un sensor de tránsito, un contador de ocupación de un estacionamiento, o una mención en redes sociales: esos datos **siguen llegando** mientras el sistema está encendido, y el sistema tiene que responder preguntas sobre ellos sin esperar a que "terminen de cargar" — porque nunca terminan.

El programa oficial del curso lo nombra así: *"Bases de datos en streaming: extracción y procesamiento de datos en streaming como sensores y redes sociales."* Redis es la primera herramienta con la que se aborda ese problema, porque resuelve la parte más urgente — la **velocidad** — antes de que en la próxima clase se aborde la otra mitad, el **volumen**, con HBase.

## 2. Qué es Redis y cómo se usa, paso a paso

### 2.1 El modelo: un servidor, y clientes que le hablan

Redis no es una librería que se importa y ya: es un **programa aparte**, llamado el **servidor**, que se queda corriendo todo el tiempo, escuchando en un puerto de red (por defecto el **6379**), esperando que alguien se conecte. Uno no "abre" Redis como se abre un archivo — uno se **conecta** a él, de la misma forma en que un navegador se conecta a un sitio web.

Para hablar con ese servidor hace falta un **cliente**: un programa que abre la conexión y manda comandos, uno a la vez, esperando la respuesta de cada uno antes de mandar el siguiente. En este laboratorio van a usar dos clientes distintos, para dos propósitos distintos:

- **`redis-cli`** — un cliente de línea de comandos, para escribir comandos a mano y ver la respuesta al tiro. Es la forma más directa de *aprender* los comandos, y es la que usa este documento en todos sus ejemplos.
- **`redis-py`** (la librería de Python, `import redis`) — para que el notebook del laboratorio hable con Redis desde código. Sus funciones son casi un calco de los comandos de `redis-cli` (sección 2.4).

Que haya un servidor y varios clientes posibles es importante para lo que viene más adelante en pub/sub y streams: **más de un cliente puede estar conectado al mismo servidor al mismo tiempo**, y eso es justamente lo que hace posible que un dato "publicado" por uno aparezca al instante en otro.

### 2.2 Conectarse con `redis-cli`

Hay dos servidores distintos a los que se van a conectar durante el laboratorio: el **Redis local** (el que levanta `docker compose up -d`, Parte 0) y el **Redis compartido del VPS**. La forma de conectarse a cada uno cambia un poco según el sistema operativo — acá las tres.

#### Camino recomendado para los tres sistemas: usar Docker

Todo el curso ya depende de Docker (los labs de PostGIS), así que apoyarse en él evita instalar un cliente nuevo, y es **exactamente el mismo comando en Windows, Mac y Linux**.

Para el Redis local, que ya corre dentro del contenedor `pmd-redis` (levantado con `docker compose up -d` en la Parte 0), basta con "entrar" a ese contenedor y ejecutar el cliente que ya trae instalado adentro:

```
docker exec -it pmd-redis redis-cli
```

- `docker exec -it pmd-redis redis-cli` — ejecuta el comando `redis-cli` **dentro** del contenedor que ya está corriendo, llamado `pmd-redis`. `-it` deja la terminal interactiva, como si `redis-cli` corriera directo en la máquina. No hace falta instalar nada aparte: la imagen de Redis ya trae el cliente adentro.

Para el Redis del VPS (que corre en otra máquina, no en un contenedor local), se levanta un contenedor **efímero** solo para esa conexión, pasándole la dirección, el puerto y la clave (la clave se da en clase y va en el archivo `.env`, sección 2.6):

```
docker run -it --rm redis:7-alpine redis-cli -h redis-stream.5.75.154.51.sslip.io -p 443 --tls --sni redis-stream.5.75.154.51.sslip.io -a <clave>
```

- `docker run -it --rm redis:7-alpine redis-cli ...` — descarga (la primera vez) y arranca un contenedor nuevo, solo para esta conexión, y dentro de él corre `redis-cli` apuntando al VPS en vez de a `localhost`. `--rm` borra el contenedor apenas se cierra — no queda nada instalado ni corriendo en la máquina.
- `-h redis-stream.5.75.154.51.sslip.io` — el **host**: la dirección del servidor. (`sslip.io` es un servicio que convierte un nombre como ese en la IP que lleva adentro, `5.75.154.51`: así el servidor tiene nombre sin tener que registrar un dominio.)
- `-p 443` — el **puerto**. No es el 6379 de siempre, a propósito: el 443 es el puerto de HTTPS, el que usa cualquier sitio web seguro, y por eso casi ninguna red (la del laboratorio incluida) lo bloquea. El 6379, en cambio, muchas redes institucionales lo cierran.
- `--tls` — la conexión va **cifrada**, igual que una página `https://`. Como el Redis del VPS está en internet y pide clave, no corresponde mandar esa clave en texto plano.
- `--sni <host>` — le dice al servidor, al abrir la conexión cifrada, **a qué nombre** se quiere hablar. En el puerto 443 del VPS conviven varios servicios (sitios web, este Redis); un intermediario (*proxy*) mira ese nombre para decidir a cuál mandar la conexión. Sin `--sni`, `redis-cli` no lo manda, el proxy no sabe que se busca a Redis, y la conexión falla con `certificate verify failed`. (La librería de Python sí lo manda sola: en el notebook no hace falta nada.)
- `-a <clave>` — la clave (*password*). `redis-cli` avisa que ponerla en la línea de comandos "puede no ser seguro" (queda en el historial de la terminal): es un aviso, no un error.

En ambos casos, si la conexión funciona, el prompt cambia a algo así (mostrando `127.0.0.1` para el Redis local, o el host del VPS para el otro):

```
127.0.0.1:6379>
```

Ese prompt es la señal de que **ya se está hablando con Redis**. **Todos los bloques de comandos de este documento, salvo que se diga explícitamente lo contrario, se escriben ahí** — no son comandos de `bash`/PowerShell, no son SQL, y no van dentro de una celda de Python (esa es harina de otra costal, ver 2.4). Para salir en cualquier momento: `exit`, o `Ctrl+D` (en Windows, `Ctrl+C` si `Ctrl+D` no corta).

#### Alternativa: instalar `redis-cli` nativo (Mac / Linux)

Quienes prefieran no pasar por Docker para esto pueden instalar el cliente directo en la máquina — **solo el cliente, no el servidor** (el servidor sigue siendo el contenedor de Docker):

```bash
# Mac (con Homebrew)
brew install redis

# Linux (Debian/Ubuntu)
sudo apt install redis-tools
```

Con eso instalado, `redis-cli` (sin `docker exec` ni `docker run` delante) funciona igual que se describe arriba, tanto contra el Redis local (`redis-cli`, sin argumentos, apunta a `localhost:6379` por defecto) como contra el del VPS (`redis-cli -h redis-stream.5.75.154.51.sslip.io -p 443 --tls --sni redis-stream.5.75.154.51.sslip.io -a <clave>` — los mismos argumentos de arriba, sin el `docker run` delante).

**En Windows no hay esta alternativa** — Redis Ltd. no distribuye un instalador oficial de `redis-cli` para Windows. Si alguien ya usa **WSL** (Windows Subsystem for Linux) puede instalar `redis-tools` ahí adentro (`sudo apt install redis-tools`, igual que en Linux) y usar `redis-cli` normalmente desde esa terminal — pero para todos los demás, el camino de Docker de arriba es el más simple y es el que se usa en el laboratorio.

### 2.3 La anatomía de un comando, y qué es una "clave"

Un comando de Redis siempre tiene la misma forma:

```
COMANDO   clave   [argumentos adicionales...]
```

- La primera palabra es el **nombre del comando** (por convención se escribe en mayúsculas en la documentación, pero Redis no distingue mayúsculas de minúsculas al ejecutarlo).
- La segunda palabra, casi siempre, es la **clave** (*key*) sobre la que se opera: una cadena de texto que identifica un dato, tal como el nombre de una variable o el nombre de un archivo. Redis no impone ninguna estructura de carpetas — pero por convención (la que se usa todo este documento y el laboratorio) se simula una jerarquía separando con dos puntos: `estacion:CC-001:ultimo_valor` se lee "estación → CC-001 → último valor", aunque para Redis es, en el fondo, una única cadena de texto plana.
- Lo que viene después depende del comando: puede ser el valor a guardar, un rango, una condición, etc. — se explica caso a caso más abajo.

### 2.4 En una palabra: Redis es un diccionario clave→valor, y lo que cambia es el TIPO de valor

Toda la sección 3 de este documento presenta distintas "estructuras de datos". Conviene tener clara la idea de fondo antes de entrar en el detalle: **Redis, en el fondo, es siempre lo mismo — una clave apunta a un valor** — y lo único que cambia entre "String", "Hash", "Lista", "Set" y "Sorted Set" es el **tipo** de valor al que esa clave puede apuntar. Cada tipo trae su propia familia de comandos (no se puede usar un comando de listas sobre una clave que guarda un hash), pero todos comparten la misma anatomía de la sección 2.3.

### 2.5 Del `redis-cli` a Python

El notebook del laboratorio no usa `redis-cli` directamente — usa la librería `redis-py`, que se instala con `pip install redis` y se importa con `import redis`. La traducción de un comando a Python es casi mecánica: el nombre del comando, en minúsculas, se vuelve el nombre de una función:

```python
import redis
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

r.set("estacion:CC-001:ultimo_valor", 42.5)   # equivale a: SET estacion:CC-001:ultimo_valor 42.5
r.get("estacion:CC-001:ultimo_valor")          # equivale a: GET estacion:CC-001:ultimo_valor
```

`decode_responses=True` hace que Python devuelva texto normal en vez de `bytes` — sin eso, cada respuesta llegaría como `b"42.5"` en vez de `"42.5"`. De aquí en adelante, este documento muestra los comandos en `redis-cli` (por claridad), pero todos tienen su equivalente directo en `r.algo(...)`.

Contra el Redis del VPS, la conexión lleva los mismos datos que en `redis-cli` (host, puerto, clave y TLS). En el notebook no se escriben a mano: se leen del archivo `.env` (sección 2.6).

```python
r = redis.Redis(host="redis-stream.5.75.154.51.sslip.io", port=443, ssl=True,
                password="<clave>", decode_responses=True)
r.ping()   # True si la conexión y la clave están bien
```

`ssl=True` es el `--tls` de `redis-cli`. El nombre para el `--sni` Python lo manda solo, a partir del `host`.

### 2.6 El entorno del laboratorio: el `.env`, el servidor compartido y los caminos de rescate

**El archivo `.env`.** Host, puerto, clave y nombre del equipo viven en un archivo de texto llamado `.env`, en la carpeta del laboratorio, con una variable por línea:

```
EQUIPO=equipo-1
VPS_HOST=redis-stream.5.75.154.51.sslip.io
VPS_PORT=443
VPS_PASS=<clave que se da en clase>
```

Se arma copiando `.env.example` (que viene en el repositorio, con la clave vacía) como `.env` y completándolo. La celda de Configuración del notebook lo lee. ¿Por qué un archivo aparte y no escribir la clave en el notebook? Porque el `.env` **no se sube a git** (está en el `.gitignore`): el código se comparte, las claves no. Es la práctica estándar en cualquier proyecto — y la que se espera en el proyecto semestral: si una clave llega a GitHub, hay que darla por pública.

**Un servidor, todo el curso.** El Redis del VPS es **uno solo** para todos los equipos a la vez. Eso tiene dos consecuencias:

- **Las claves propias llevan el nombre del equipo adelante.** Si el equipo 1 hace `SET estacion:CC-001:ultimo_valor 42.5` y el equipo 2 hace lo mismo con otro valor, el segundo pisa al primero: para Redis es la misma clave. Por eso en la Parte 1 del notebook todas las claves empiezan con `equipo-N:` (por ejemplo `equipo-1:estacion:CC-001:ultimo_valor`). Redis no tiene "tablas" ni "esquemas" que separen los datos de cada uno: el separador (*namespace*) va en el propio nombre de la clave.
- **Hay comandos bloqueados.** Para que nadie borre por accidente el stream que usa todo el curso, en el VPS la cuenta de los alumnos **no puede** ejecutar `DEL`, `FLUSHALL`, `XADD`, `XTRIM`, `XDEL`, `EXPIRE` ni `XGROUP DESTROY`, entre otros. Si lo intentan, Redis responde `NOPERM User default has no permissions to run the '...' command`. No es un error del laboratorio: es Redis aplicando permisos por usuario (**ACL**, *access control list*). En el Redis local no hay restricciones — es de cada equipo.

**Los mismos datos.**

| | Dónde está Redis | Cómo se conecta el notebook |
|---|---|---|
| **1. VPS** (el normal) | en un servidor en internet, con el generador corriendo 24/7 | `VPS_HOST` / `VPS_PORT=443` del `.env`, con TLS |
| **2. Rescate local** | en la misma máquina, en el contenedor `pmd-redis` | automático: si el VPS no responde en 3 s, la Parte 0 hace `docker compose up -d` y reproduce `datos/gran_concepcion_stream.parquet` |

Usan la misma lógica de generación (`generador.py`, con la misma semilla), así que los datos se ven igual. Lo único que se pierde en el camino 2 es la escala de la Parte 3: los consumer groups se prueban con 2–3 consumidores dentro del equipo en vez de con todo el curso.

---

## 3. Las estructuras de datos de Redis

### 3.1 Strings: lo más simple — una clave, un valor

Una clave apunta a un único valor de texto (o número, que Redis trata como texto hasta que hay que hacer aritmética con él).

```
SET estacion:CC-001:ultimo_valor 42.5
GET estacion:CC-001:ultimo_valor
```

- `SET <clave> <valor>` — guarda `42.5` bajo la clave `estacion:CC-001:ultimo_valor`. Si la clave ya existía, la reemplaza. Si no existía, la crea. No hay que "declararla" antes.
- `GET <clave>` — pide de vuelta el valor guardado bajo esa clave. La respuesta esperada, en este caso, es `"42.5"`.
- Si se hace `GET` sobre una clave que no existe, Redis responde `(nil)` — el equivalente de Redis a `None`/`null`.

```
INCR estacion:CC-001:contador
INCR estacion:CC-001:contador
GET estacion:CC-001:contador
```

- `INCR <clave>` — suma 1 al valor de esa clave (si no existía, parte de 0). El resultado esperado tras dos `INCR` y un `GET` es `"2"`.
- Es una operación **atómica**: si diez procesos hacen `INCR` sobre la misma clave al mismo tiempo, Redis los procesa uno por uno y ninguno se pisa — no hay condición de carrera, a diferencia de leer un valor, sumarle 1 en el programa, y volver a guardarlo.

### 3.2 TTL: la clave que se autodestruye

Cualquier clave de Redis — sin importar el tipo de valor que guarde — puede tener un **tiempo de vida**. Al cumplirse, Redis la borra sola, sin que nadie tenga que pedirlo.

```
SET estacion:CC-001:ultimo_valor 42.5 EX 60
TTL estacion:CC-001:ultimo_valor
```

- `EX 60`, agregado al final del `SET`, le dice a Redis: "esta clave expira en 60 segundos desde ahora". Es parte del mismo comando `SET`, no uno aparte.
- `TTL <clave>` — pregunta cuántos segundos le quedan de vida a una clave. Devuelve el número de segundos restantes, o `-1` si la clave no tiene TTL (nunca expira), o `-2` si la clave ya no existe (expiró, o nunca se creó).
- Si se espera más de 60 segundos y se hace `GET estacion:CC-001:ultimo_valor`, la respuesta es `(nil)` — la clave desapareció sola.

Esto es nuevo frente a todo lo visto en PostGIS: una comuna o una estación de metro no caducan. Una **lectura** de un sensor de tránsito, sí — un valor de "hace 20 minutos" ya no describe el tránsito actual, y quererlo borrar automáticamente (en vez de acumular lecturas viejas para siempre) es parte del diseño, no un descuido.

### 3.3 Hashes: la ficha de una entidad

*(Aclaración de vocabulario: un "hash" de Redis no tiene nada que ver con una función criptográfica de hash. Acá "hash" significa "diccionario" o "mapa" — un conjunto de pares campo→valor guardados bajo una sola clave, como un objeto de JSON con varias propiedades.)*

```
HSET estacion:CC-001 nombre "Plaza Independencia" comuna "Concepción" tipo "flujo_vehicular"
HGETALL estacion:CC-001
HGET estacion:CC-001 comuna
```

- `HSET <clave> <campo1> <valor1> <campo2> <valor2> ...` — bajo la clave `estacion:CC-001`, guarda tres campos (`nombre`, `comuna`, `tipo`) con sus valores. Se pueden agregar tantos pares campo-valor como se quiera, en el mismo comando o en comandos separados.
- `HGETALL <clave>` — devuelve **todos** los campos y valores guardados bajo esa clave, como una lista alternada `campo, valor, campo, valor, ...`.
- `HGET <clave> <campo>` — devuelve el valor de **un solo campo**, sin traer los demás. Esperado: `"Concepción"`.

Es la estructura natural para guardar el **estado actual** de una entidad (la ficha de una estación, con todos sus datos descriptivos) — algo parecido a una fila de una tabla, pero sin que todas las claves de tipo Hash tengan que compartir las mismas columnas entre sí.

### 3.4 Listas: una bitácora en orden

Una lista guarda varios valores **en un orden específico**, y permite agregar o quitar elementos de forma eficiente en cualquiera de los dos extremos.

```
LPUSH estacion:CC-001:log 38 41 42.5
LRANGE estacion:CC-001:log 0 9
```

- `LPUSH <clave> <valor1> <valor2> ...` — inserta valores **al inicio** de la lista (por eso "L" de *left*). Insertar `38`, luego `41`, luego `42.5` en ese orden dentro del mismo comando deja la lista, de más nuevo a más viejo, como: `42.5, 41, 38`.
- `LRANGE <clave> <inicio> <fin>` — devuelve un rango de la lista por posición, empezando en `0` (el primer elemento). `LRANGE ... 0 9` pide "desde la posición 0 hasta la posición 9" — es decir, hasta los primeros 10 elementos. Con solo tres valores cargados, el resultado esperado es la lista completa: `42.5, 41, 38`.

```
LTRIM estacion:CC-001:log 0 99
```

- `LTRIM <clave> <inicio> <fin>` — **recorta** la lista, quedándose solo con el rango indicado y descartando el resto. `LTRIM ... 0 99` deja como máximo los 100 elementos más recientes, tirando todo lo demás. Es la forma de evitar que una lista que recibe datos sin parar (como un log de lecturas) crezca para siempre y termine ocupando toda la RAM.

### 3.5 Sets: colecciones sin orden ni repetidos

Un set guarda un conjunto de valores únicos, sin ningún orden particular, y trae las operaciones clásicas de teoría de conjuntos.

```
SADD activos:min_actual CC-001 TAL-001 HUA-002 PEN-001
SADD activos:min_anterior CC-001 TAL-001 HUA-002 COR-001
```

- `SADD <clave> <valor1> <valor2> ...` — agrega uno o más valores al set. Si un valor ya estaba, no pasa nada (por eso "sin repetidos": agregar `CC-001` dos veces deja el set exactamente igual que agregarlo una vez).

```
SINTER activos:min_actual activos:min_anterior
SDIFF activos:min_anterior activos:min_actual
```

- `SINTER <clave1> <clave2>` — la **intersección**: los valores que están en ambos sets a la vez. Con los datos de arriba, el resultado esperado es `CC-001, TAL-001, HUA-002` (las tres que aparecen en los dos comandos `SADD`).
- `SDIFF <clave1> <clave2>` — la **diferencia**: los valores que están en el primer set pero no en el segundo. `SDIFF activos:min_anterior activos:min_actual` pregunta "¿quién estaba activo antes, y ya no aparece ahora?" — el resultado esperado es `COR-001`.

`SDIFF` entre dos ventanas de tiempo consecutivas es, en una sola línea, la forma más simple de detectar una estación que dejó de reportar.

### 3.6 Sorted Sets (ZSET): un ranking que Redis mantiene ordenado

Como un set (valores únicos), pero cada valor tiene además un **puntaje** (`score`) numérico asociado, y Redis guarda el conjunto siempre ordenado por ese puntaje — sin que haya que pedirle "ordena" cada vez.

```
ZADD ranking:congestion 45 CC-001 78 HUA-002 30 TAL-001 92 SPP-002
ZREVRANGE ranking:congestion 0 4 WITHSCORES
```

- `ZADD <clave> <puntaje1> <valor1> <puntaje2> <valor2> ...` — agrega valores con su puntaje. Acá se agregan cuatro estaciones, cada una con su nivel de congestión (`CC-001`→45, `HUA-002`→78, etc.).
- `ZREVRANGE <clave> <inicio> <fin> WITHSCORES` — devuelve un rango del ranking, ordenado de **mayor a menor** puntaje (por eso "REV", de *reverse*), incluyendo los puntajes en la respuesta. `0 4` pide las primeras 5 posiciones (posición 0 a la 4). Esperado: `SPP-002` (92) primero, luego `HUA-002` (78), luego `CC-001` (45), luego `TAL-001` (30).

```
ZINCRBY ranking:congestion 15 CC-001
```

- `ZINCRBY <clave> <cantidad> <valor>` — le suma `15` al puntaje actual de `CC-001` (quedaría en 60), sin tener que leer el puntaje viejo primero. Repetir el `ZREVRANGE` de arriba después de esto muestra el ranking ya reordenado solo.

Un ranking en vivo (más congestionado, más mencionado, más reciente) es exactamente el caso de uso: mantener un orden que cambia constantemente sin tener que ordenar de nuevo cada vez, a mano, en el cliente.

---

## 4. Pub/Sub: la mensajería efímera

Pub/Sub (*publish/subscribe*, publicar/suscribirse) es el mecanismo más simple de Redis para pasar mensajes entre clientes **en el momento en que ocurren**, sin guardarlos. Hacen falta **dos clientes conectados al mismo tiempo** — por eso el ejercicio se hace con dos terminales abiertas en paralelo, cada una con su propio `redis-cli` conectado al mismo servidor.

```
-- Terminal A (el suscriptor — queda "colgado" esperando mensajes)
SUBSCRIBE sensores:flujo_vehicular
```

- `SUBSCRIBE <canal>` — le dice a Redis "avísame apenas alguien publique algo en el canal `sensores:flujo_vehicular`". El cliente que ejecuta esto queda **bloqueado**: no vuelve a mostrar un prompt normal, se queda esperando. Es intencional — es lo que hace posible recibir mensajes en tiempo real.

```
-- Terminal B (el publicador — manda el mensaje y sigue funcionando normal)
PUBLISH sensores:flujo_vehicular '{"estacion":"CC-001","valor":42.5}'
```

- `PUBLISH <canal> <mensaje>` — envía el texto indicado (acá, un JSON como texto plano — a Redis no le importa el formato, solo lo reenvía) a todos los clientes que en ese instante están suscritos a ese canal.
- **Apenas se ejecuta el `PUBLISH` en la Terminal B, el mensaje aparece solo en la Terminal A** — sin que nadie tenga que pedirlo ahí. Ese es el efecto que hay que ver para entender pub/sub: es un *broadcast* instantáneo.

**El límite, y por qué importa:** si en el momento del `PUBLISH` no había ningún cliente con un `SUBSCRIBE` activo en ese canal, **el mensaje se pierde para siempre**. Redis no lo guarda en ninguna parte — no hay como "ponerse al día" suscribiéndose después. El Ejercicio 2.2 del laboratorio lo comprueba a propósito: se apaga el suscriptor, se sigue publicando, se prende de nuevo, y lo publicado durante el apagón no aparece por ningún lado.

Pub/Sub sirve para avisos donde perderse uno ocasional no tiene consecuencias graves (por ejemplo, "invalida tu caché, algo cambió"). No sirve para nada que necesite **recuperar** lo perdido — que es exactamente lo que necesita un sistema de monitoreo de sensores. Ese problema lo resuelve la siguiente estructura.

## 5. Redis Streams: el log durable

Un Stream es, para efectos de este documento, un **quinto tipo de valor** de Redis (además de string, hash, lista y set/zset), pensado específicamente para resolver lo que Pub/Sub no puede: un registro de eventos que se puede **guardar, leer después, y repartir entre varios lectores**.

### 5.1 Escribir: `XADD`

```
XADD sensores:flujo * estacion CC-001 valor 42.5
```

- `XADD <clave> <id> <campo1> <valor1> <campo2> <valor2> ...` — agrega una entrada nueva al final del stream `sensores:flujo`, con los campos `estacion` y `valor` (tantos pares campo-valor como se necesiten, igual que en un Hash).
- El `*` en el lugar del `<id>` le pide a Redis que **genere el identificador automáticamente**. Ese ID tiene la forma `<milisegundos-desde-1970>-<número de secuencia>` — por ejemplo `1758790992123-0` — y es **siempre creciente**: cada entrada nueva tiene un ID mayor que la anterior. Ese orden estricto es lo que permite, más adelante, pedir "todo lo que llegó entre este momento y este otro".
- A diferencia de `LPUSH` (sección 3.4), lo escrito con `XADD` **no se pierde ni hay que recortarlo a mano para conservarlo** — queda guardado como parte del stream hasta que alguien lo borre explícitamente (o se use `XTRIM`, mencionado en la sección 8).

### 5.2 Leer lo ya guardado: `XRANGE` / `XREVRANGE`

```
XRANGE sensores:flujo - +
```

- `XRANGE <clave> <desde> <hasta>` — devuelve las entradas del stream cuyo ID cae en ese rango. Los símbolos `-` y `+` son atajos para "el ID más chico posible" y "el ID más grande posible" — juntos, piden **todo el stream**, de la entrada más vieja a la más nueva.

```
XRANGE sensores:flujo 1758790900000 1758791000000
```

- Reemplazando `-`/`+` por dos timestamps (en milisegundos), se pide una **ventana de tiempo exacta** — por ejemplo, exactamente los 20 segundos del experimento de pub/sub de la sección 4. Esto es lo que Pub/Sub no puede hacer: reconstruir una ventana de tiempo pasada, aunque nadie haya estado "escuchando" en ese momento.

```
XREVRANGE sensores:flujo + - COUNT 10
```

- `XREVRANGE` es igual que `XRANGE` pero **al revés** (de la entrada más nueva a la más vieja) — por eso acá el orden de los argumentos también se invierte (`+` primero, `-` después). `COUNT 10` limita el resultado a las últimas 10 entradas, en vez de traer el stream completo.

### 5.3 Leer en vivo: `XREAD`

```
XREAD BLOCK 5000 STREAMS sensores:flujo $
```

- `XREAD ... STREAMS <clave> <desde-id>` — pide leer del stream a partir de un ID. El símbolo `$` significa "todavía no existe ninguna entrada con este ID — dame solo lo que llegue **de ahora en adelante**".
- `BLOCK 5000` le dice al cliente que, si no hay nada nuevo todavía, **espere hasta 5000 milisegundos (5 segundos)** antes de responder vacío, en vez de responder vacío al tiro. Mientras espera, el cliente queda bloqueado — parecido al `SUBSCRIBE` de pub/sub, pero leyendo de un stream en vez de un canal.
- **Diferencia clave con Pub/Sub:** si dos clientes distintos hacen este mismo `XREAD` al mismo tiempo, contra el mismo stream, **ambos reciben las mismas entradas nuevas** — no hay reparto de trabajo. Para repartir el trabajo entre varios lectores hace falta la siguiente idea.

### 5.4 Consumer Groups: repartir el trabajo entre varios lectores

Un *consumer group* (grupo de consumidores) es un mecanismo de Redis para que **varios clientes se repartan** las entradas de un mismo stream, de forma que cada entrada la procese **un solo miembro del grupo** — no todos, como pasaría con un `XREAD` simple.

Una analogía útil: es como una bandeja de tickets de soporte compartida por un equipo. Cada ticket nuevo se le asigna a **una sola persona** del equipo, y queda registrado quién lo tomó, para que se pueda saber si alguien lo dejó sin resolver.

```
XGROUP CREATE sensores:flujo curso-pmd $
```

- `XGROUP CREATE <clave> <nombre-del-grupo> <desde-id>` — crea el grupo `curso-pmd` sobre el stream `sensores:flujo`. El `$` le dice que el grupo debe empezar a repartir **solo entradas nuevas a partir de este momento**, ignorando lo que ya estaba en el stream antes de crear el grupo. Este comando se ejecuta **una sola vez** (si se repite sobre el mismo grupo, Redis devuelve un error diciendo que ya existe).

```
XREADGROUP GROUP curso-pmd equipo-3 COUNT 5 STREAMS sensores:flujo >
```

- `XREADGROUP GROUP <grupo> <nombre-del-consumidor> COUNT <n> STREAMS <clave> >` — le pide a Redis, dentro del grupo `curso-pmd`, hasta `5` entradas para el consumidor llamado `equipo-3` (cada equipo/persona usa un nombre distinto acá, para que Redis pueda repartir). El símbolo `>` significa "dame entradas que **todavía no se le hayan entregado a nadie del grupo**".
- Si otro cliente, con el nombre `equipo-7`, ejecuta el mismo comando (cambiando solo el nombre del consumidor) contra el mismo stream y grupo, **recibe entradas distintas** a las que recibió `equipo-3` — ahí está el reparto.

```
XACK sensores:flujo curso-pmd 1758790992123-0
```

- `XACK <clave> <grupo> <id-de-la-entrada>` — confirma que esa entrada específica **ya fue procesada**. Hasta que se haga este `XACK`, la entrada queda marcada como **pendiente** para el consumidor que la recibió.

```
XPENDING sensores:flujo curso-pmd
```

- `XPENDING <clave> <grupo>` — muestra un resumen de todo lo que quedó **entregado pero sin confirmar** dentro del grupo: cuántas entradas, cuáles son, y a qué consumidor se le asignó cada una. Es la forma de detectar trabajo que quedó a medio hacer.

```
XCLAIM sensores:flujo curso-pmd equipo-2 60000 1758790992123-0
```

- `XCLAIM <clave> <grupo> <nuevo-consumidor> <tiempo-mínimo-ms> <id>` — reasigna una entrada pendiente a otro consumidor (acá, `equipo-2`), siempre que lleve al menos el tiempo indicado (`60000` ms = 60 segundos) sin confirmarse. Es el mecanismo para "rescatar" trabajo de un consumidor que se cayó o quedó pegado.

Ese ciclo — pedir con `XREADGROUP`, procesar, confirmar con `XACK`, y poder reclamar con `XCLAIM` lo que nadie confirmó — es lo que le da a Streams una garantía que ni Pub/Sub ni las Listas tienen por sí solas: **nada se pierde silenciosamente**, incluso si el consumidor que lo recibió se cae a mitad de camino.

### 5.5 Dos relojes: cuándo midió el sensor y cuándo llegó el dato

Cada entrada del stream del laboratorio tiene **dos horas**, y no siempre coinciden:

- El **ID** (`1790301020225-0`) lo pone Redis al hacer `XADD`: dice **cuándo llegó** el dato al servidor (*processing time*).
- El campo **`timestamp`** lo pone el sensor: dice **cuándo midió** (*event time*).

En un mundo ideal serían iguales. En el real no: un sensor pierde la conexión un minuto y después manda de golpe lo que tenía guardado, o reintenta un envío y el mismo dato llega **dos veces**. El generador del laboratorio imita las dos cosas a propósito: cerca de un 3% de las lecturas llega con un `timestamp` de 30 a 120 segundos atrás (**tardías**) y cerca de un 2% se envía **repetida**.

Para la pregunta "¿cuál fue el promedio de flujo entre las 09:00 y las 09:05?", lo que manda es el `timestamp`: una lectura tardía pertenece al minuto en que se midió, no al minuto en que llegó. Y las repetidas hay que sacarlas antes de promediar (por ejemplo, quedándose con una sola lectura por `estacion_id` + `timestamp`). Redis no hace ninguna de las dos cosas por uno: para el stream, dos entradas con el mismo contenido son dos entradas distintas, con IDs distintos. Esta distinción entre *event time* y *processing time* aparece en todo sistema de streaming.

---

## 6. Cuándo usar cada estructura

| Necesito... | Uso | Por qué |
|---|---|---|
| El valor más reciente de algo, que puede caducar | **String + TTL** | Simplicidad; Redis borra solo lo vencido |
| El estado completo de una entidad | **Hash** | Varios campos, una sola clave, lectura/escritura parcial |
| Un ranking que cambia constantemente | **Sorted Set** | Orden mantenido por Redis, sin reordenar a mano |
| Avisar algo que ocurrió, sin que importe perderse alguno | **Pub/Sub** | Simplicidad máxima, cero almacenamiento |
| Un historial que hay que poder reconstruir o repartir entre consumidores | **Streams** | Durable, con IDs ordenados y consumer groups |

## 7. Redis frente a lo demás visto en el curso

Frente a PostgreSQL/PostGIS (Clases 3-5): PostGIS optimiza consultas complejas y garantiza durabilidad sobre datos que cambian poco; Redis optimiza latencia sobre datos que cambian todo el tiempo, sacrificando por defecto la durabilidad estricta. No son competidores — un sistema real (y el proyecto semestral) puede perfectamente usar PostGIS para el catastro de estaciones y Redis para sus lecturas en vivo.

Frente a HBase (próxima clase): Redis resuelve **velocidad** — miles de lecturas y escrituras por segundo, todo en RAM. HBase resuelve **volumen** — miles de millones de filas, distribuidas en disco entre varios nodos. La pregunta que separa a uno del otro no es "¿es streaming o no?", sino **¿necesito la última hora en microsegundos, o necesito los últimos cinco años, y me alcanza con milisegundos?**

## 8. Persistencia y límites de Redis

Aunque Redis vive en RAM, puede persistir a disco de dos formas — no se usan hoy en el laboratorio (el ejercicio de pub/sub necesita que lo publicado sea volátil), pero vale la pena conocerlas:

- **RDB (snapshot):** copia completa de la memoria a disco cada cierto tiempo o número de cambios. Rápido de restaurar, pero se puede perder lo escrito desde el último snapshot.
- **AOF (append-only file):** cada comando de escritura se registra en un archivo de log, que se puede "reproducir" para reconstruir el estado. Más durable, más lento.

Y los límites, dichos en voz alta, porque elegir bien la herramienta es parte de aprenderla:

- **El tamaño de los datos está limitado por la RAM.** Un stream que crece sin límite eventualmente no cabe — en producción se usa `XTRIM` para acotarlo (recorta un stream igual que `LTRIM` recorta una lista), o se archiva a otra base (como HBase) lo que ya no necesita estar en memoria.
- **No es la herramienta para consultas analíticas complejas.** "¿Cuál fue el promedio de flujo vehicular por comuna cada hora, durante el último mes?" es una pregunta para una base de datos de disco (relacional, columnar, o NoSQL con historial completo), no para Redis.
- **La replicación y el clustering existen, pero no se ven en este curso.** Todo lo de hoy corre en una sola instancia — suficiente para entender el modelo, no para producción a gran escala.

## 9. Glosario

- **Servidor / cliente:** el servidor es el proceso de Redis que guarda los datos y escucha conexiones; el cliente (`redis-cli`, `redis-py`, etc.) es el programa que se conecta y manda comandos.
- **Clave (*key*):** el nombre, en texto, bajo el que se guarda un dato — el primer argumento de casi todos los comandos.
- **En memoria (*in-memory*):** los datos viven en RAM, no en disco, por defecto.
- **TTL (*time to live*):** tiempo restante antes de que una clave expire y Redis la borre.
- **Pub/Sub:** patrón de mensajería donde un publicador envía a un canal y los suscritos reciben en vivo, sin almacenamiento.
- **Stream:** estructura de log apendable de Redis, con entradas identificadas por ID creciente.
- **Consumer group:** conjunto de consumidores que se reparten las entradas de un stream, cada una procesada por uno solo.
- **ACK (*acknowledge*):** confirmación de que una entrada fue procesada; libera su estado de "pendiente".
- **Streaming:** procesamiento de datos que llegan de forma continua, sin un tamaño total conocido de antemano.
- **Event time / processing time:** la hora en que ocurrió (o se midió) un evento, frente a la hora en que el sistema lo recibió. En el laboratorio: el campo `timestamp` frente al ID de la entrada.
- **ACL (*access control list*):** permisos por usuario en Redis — qué comandos puede ejecutar cada cuenta y sobre qué claves.
- **TLS:** el cifrado de una conexión de red (lo que pone la "s" en `https`). En `redis-cli` se activa con `--tls`; en `redis-py`, con `ssl=True`.
- **`.env`:** archivo de variables de configuración (host, puerto, claves) que se deja fuera del control de versiones para no publicar credenciales.

## 10. Referencias

- Documentación oficial de Redis: <https://redis.io/docs/latest/>
- Referencia de comandos (uno por uno, con ejemplos): <https://redis.io/docs/latest/commands/>
- Redis Streams (guía oficial): <https://redis.io/docs/latest/develop/data-types/streams/>
- Texto guía del curso: Bahga, A. & Madisetti, V. (2016). *Big Data Science & Analytics: A Hands-On Approach*, VPT.
