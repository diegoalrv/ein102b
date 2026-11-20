-- Laboratorio 11: las cuatro tablas. Las crea el compose al iniciar Postgres con el volumen vacío.
--   eventos          → la escribe Airflow (cargar, en eventos_por_hora): la misma tabla de la C14
--   resumen_horario  → la escribe Airflow (resumir, en eventos_por_hora): una fila por hora y estación
--   resumen_diario   → la escribe Airflow (resumir_dia, en resumen_diario): una fila por día y estación
--   alertas          → la escribe n8n (nodo Postgres del workflow alerta_aire_postgres)
-- Las claves primarias son las que hacen idempotente todo: con ON CONFLICT, repetir una
-- tarea (un Clear) o un aviso (el mismo webhook dos veces) no duplica nada.
CREATE TABLE eventos (
  estacion_id text, tipo_sensor text, valor double precision, ts timestamptz,
  PRIMARY KEY (estacion_id, ts)
);
CREATE TABLE resumen_horario (
  hora timestamptz, estacion_id text, tipo_sensor text, n int, promedio double precision,
  PRIMARY KEY (hora, estacion_id)
);
CREATE TABLE resumen_diario (
  dia date, estacion_id text, tipo_sensor text, n int, promedio double precision,
  PRIMARY KEY (dia, estacion_id)
);
CREATE TABLE alertas (
  hora timestamptz, estacion_id text, promedio double precision,
  PRIMARY KEY (hora, estacion_id)
);
