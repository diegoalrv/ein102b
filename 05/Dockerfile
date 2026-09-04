# La misma imagen de todo el semestre, más las herramientas de línea de comandos
# de GDAL (ogr2ogr, ogrinfo) y las de PostGIS (shp2pgsql, pgsql2shp).
#
# Por qué: postgis/postgis:16-3.4 trae el MOTOR (PostGIS ya usa la biblioteca
# GDAL para raster), pero no los BINARIOS de cliente. Instalarlos aquí pesa
# unos pocos MB y evita instalar GDAL en cada máquina del laboratorio.
#
# Se construye una vez, antes de la clase (necesita red para el apt-get):
#     docker compose build
FROM postgis/postgis:16-3.4

RUN apt-get update \
 && apt-get install -y --no-install-recommends gdal-bin postgis \
 && rm -rf /var/lib/apt/lists/*
