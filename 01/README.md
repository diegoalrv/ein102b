# Laboratorio 01 — Clase 1 (Vie 07-ago): Fuentes de datos masivos

> Material práctico de la sesión. El libreto de las diapositivas está en `Clases/Clase 01/Libreto_Clase1_ClaudeDesign.md` (relativo a la raíz del curso, fuera de este repositorio).

## Cómo crear los datos

Los archivos de datos **no están en el repositorio**: se generan. Es el primer paso, antes de abrir el notebook.

Desde esta carpeta (`01/`):

```bash
python3 generar_muestras.py
```

Eso produce las cinco muestras del laboratorio — `demo_chico.csv`, `muestra_A.geojson`, `muestra_B.ndjson`, `muestra_C_nodos.csv` y `muestra_C_aristas.csv` — y al terminar las verifica, imprimiendo algo así:

```
Verificación OK: 22 features · 300 eventos (19 sin pm25, 12 con -999, 12 con batería) · 15 nodos y 30 aristas · 1.000 viajes
```

Si no ves esa línea, algo falló y el notebook no va a funcionar. Sin argumentos respeta los archivos que ya existan; con `--forzar` los sobrescribe.

Falta un archivo más, el dataset grande de la Parte 1, que `generar_muestras.py` **no** genera porque pesa demasiado:

```bash
python3 generar_dataset_grande.py 2000000    # 2M filas, ~120 MB, cerca de un minuto
python3 generar_dataset_grande.py            # 10M filas, ~600 MB, unos minutos
```

No hace falta correrlo a mano: el propio notebook lo genera en su celda correspondiente, con 2M filas. Hacerlo antes solo te ahorra la espera en clase.

Desde cero, partiendo de nada:

```bash
git clone https://github.com/diegoalrv/ein102b.git && cd ein102b/01 && python3 generar_muestras.py
```

> Las muestras A y C son fixtures fijas y van escritas como literales en el script, porque el laboratorio depende de su estructura exacta: la zona de restricción **no contiene ninguna estación** (verificado con PostGIS 3.4; es a propósito, el Ej. 3.1 del Lab 02 lo usa para discutir *resultado vacío ≠ consulta mala*, y la ruta sí la cruza), y el grafo tiene que tener a "Rutas Inteligentes" como proyecto más conectado. La muestra B y `demo_chico.csv` usan semilla fija, así que también son iguales en todas las máquinas.

## Demo comparativa (bloque 2, 08:50–09:25)

- `demo_chico.csv` — 1.000 viajes simulados (Gran Valparaíso), ~55 KB.
- `demo_grande.csv` — el mismo esquema a otra escala. 10M filas es la corrida **proyectada**; 2M es lo que corren los equipos (ver *Cómo crear los datos*). **Generarlo antes de la clase.**
- `demo_comparativa.py` — corre la misma consulta (promedio de duración por zona de origen) sobre cualquiera de los dos archivos e imprime tiempo de carga, tiempo de consulta y memoria pico. Requiere `pandas`.

Secuencia en clase: pedir predicciones → correr con `demo_chico.csv` → correr con `demo_grande.csv` → completar la tabla de la diapositiva 10.

> **Por qué los equipos usan 2M y no 10M:** 10M filas × ~25 equipos son ~15 GB de disco en el laboratorio, y el DataFrame resultante pide varios GB de RAM por máquina — con riesgo real de que el kernel muera antes del Ejercicio 1.5. Con 2M se ve exactamente el mismo efecto. Si alcanzas a dejar `demo_grande.csv` ya copiado en cada máquina, mejor todavía.

## Tres muestras de reconocimiento (bloque 3, 09:40–10:15)

Entregar a los equipos **sin decir de qué tipo son** (la revelación es en la cátedra, diapositiva 14):

- `muestra_A.geojson` — geoespacial: 20 estaciones de monitoreo (puntos) + 1 zona (polígono) + 1 ruta (línea). La columna `comuna` está asignada sin cuidado: no coincide ni con el nombre de la estación ni con dónde cae el punto (Muelle Prat figura en Quilpué; "Curauma" cae a ~12 km de Curauma). Sirve para practicar `GROUP BY`, no para creerle — declararlo en clase si alguien lo nota, y guardarlo como pregunta del bloque geoespacial (¿el atributo coincide con la geometría?).
- `muestra_B.ndjson` — stream de sensores: 300 eventos **desordenados en el tiempo**, con lecturas perdidas, valores de error (-999) y campos que solo algunos sensores envían. Esas imperfecciones son a propósito: son lo que rompe el modelo relacional.
- `muestra_C_nodos.csv` + `muestra_C_aristas.csv` — grafo: 15 nodos (personas, organizaciones y proyectos) y 30 aristas conectadas por TRABAJA_EN, PARTICIPA_EN, COLABORA_CON y FINANCIA.

## Notebooks

- `lab01_estudiantes.ipynb` — el del laboratorio. 11 celdas con `# Escribe tu código aquí`.

La versión docente (soluciones, tiempos por bloque y respuestas esperadas) no está en este repositorio.

## Checklist restante (de la página de Notion)

- [ ] Verificar Docker en Lab. de Informática 2 **antes** del viernes
- [ ] Generar `demo_grande.csv` en el equipo del profesor
- [ ] Generar diapositivas con el libreto (`Clases/Clase 01/Libreto_Clase1_ClaudeDesign.md`) en Claude Design
- [ ] Plantilla de registro por equipos (pendiente)
