# Laboratorios — Procesamiento Masivo de Datos

**ELE051-B / EIN102B** · USM 2026-2 · Paralelo 701

Código e instrucciones de los laboratorios del curso. Un directorio por laboratorio.

| Lab | Clase | Tema |
|---|---|---|
| [`01/`](01/) | Vie 07-ago-2026 | Fuentes de datos masivos: escala, geoespacial, streams y grafos |

## Empezar

```bash
git clone https://github.com/diegoalrv/ein102b.git && cd ein102b/01 && python3 generar_muestras.py
```

Los datos no están versionados: el `.gitignore` excluye `*.csv`, `*.ndjson` y `*.geojson`, y cada laboratorio trae su propio generador con semilla fija. El generador verifica lo que produce y falla ruidosamente si algo no cuadra, así que si termina sin la línea `Verificación OK`, no sigas. Las instrucciones completas están en el README de cada laboratorio.

## Requisitos

- Python 3.11+ con `pandas`, `matplotlib` y `jupyter`
- Docker (se usa durante todo el semestre — conviene verificar `docker run hello-world` antes de la primera sesión)

## Versión docente

Los notebooks `*_docente.ipynb` traen las soluciones resueltas y las respuestas esperadas de la cátedra. Son la referencia del profesor: se aprende bastante más intentando los ejercicios primero.
