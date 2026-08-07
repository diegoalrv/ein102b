# Laboratorio 01 — Clase 1 (Vie 07-ago): Fuentes de datos masivos

> Material práctico de la sesión. El libreto de las diapositivas está en `Clases/Clase 01/Libreto_Clase1_ClaudeDesign.md` (relativo a la raíz del curso, fuera de este repositorio).

## ⚠️ Los datos no están versionados

Este repositorio trae **código e instrucciones**, no los archivos de datos. Antes de correr los notebooks hay que dejar en esta misma carpeta:

`demo_chico.csv` · `muestra_A.geojson` · `muestra_B.ndjson` · `muestra_C_nodos.csv` · `muestra_C_aristas.csv`

(`demo_grande.csv` no se copia: lo genera el propio notebook.)

## Demo comparativa (bloque 2, 08:50–09:25)

- `demo_chico.csv` — 1.000 viajes simulados (Gran Valparaíso), ~55 KB.
- `generar_dataset_grande.py` — genera `demo_grande.csv`. **Ejecutar antes de la clase.**
  - `python3 generar_dataset_grande.py` → 10M filas, ~600 MB, unos minutos. Es la corrida **proyectada**.
  - `python3 generar_dataset_grande.py 2000000` → 2M filas, ~120 MB, cerca de un minuto. Es lo que corren los equipos.
- `demo_comparativa.py` — corre la misma consulta (promedio de duración por zona de origen) sobre cualquiera de los dos archivos e imprime tiempo de carga, tiempo de consulta y memoria pico. Requiere `pandas`.

Secuencia en clase: pedir predicciones → correr con `demo_chico.csv` → correr con `demo_grande.csv` → completar la tabla de la diapositiva 10.

> **Por qué los equipos usan 2M y no 10M:** 10M filas × ~25 equipos son ~15 GB de disco en el laboratorio, y el DataFrame resultante pide varios GB de RAM por máquina — con riesgo real de que el kernel muera antes del Ejercicio 1.5. Con 2M se ve exactamente el mismo efecto. Si alcanzas a dejar `demo_grande.csv` ya copiado en cada máquina, mejor todavía.

## Tres muestras de reconocimiento (bloque 3, 09:40–10:15)

Entregar a los equipos **sin decir de qué tipo son** (la revelación es en la cátedra, diapositiva 14):

- `muestra_A.geojson` — geoespacial: 20 estaciones de monitoreo (puntos) + 1 zona (polígono) + 1 ruta (línea).
- `muestra_B.ndjson` — stream de sensores: 300 eventos **desordenados en el tiempo**, con lecturas perdidas, valores de error (-999) y campos que solo algunos sensores envían. Esas imperfecciones son a propósito: son lo que rompe el modelo relacional.
- `muestra_C_nodos.csv` + `muestra_C_aristas.csv` — grafo: 15 nodos (personas, organizaciones y proyectos) y 30 aristas conectadas por TRABAJA_EN, PARTICIPA_EN, COLABORA_CON y FINANCIA.

## Notebooks

- `lab01_estudiantes.ipynb` — el que reciben los equipos. 11 celdas con `# Escribe tu código aquí`, sin soluciones.
- `lab01_docente.ipynb` — **no distribuir**: mismas consignas con las soluciones resueltas, tiempos por bloque y respuestas esperadas.

## Checklist restante (de la página de Notion)

- [ ] Verificar Docker en Lab. de Informática 2 **antes** del viernes
- [ ] Generar `demo_grande.csv` en el equipo del profesor
- [ ] Generar diapositivas con el libreto (`Clases/Clase 01/Libreto_Clase1_ClaudeDesign.md`) en Claude Design
- [ ] Plantilla de registro por equipos (pendiente)
