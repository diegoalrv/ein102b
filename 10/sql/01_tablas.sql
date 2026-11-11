-- Laboratorio 10: la tabla destino de PutDatabaseRecord.
-- La clave primaria (estacion_id, ts) es lo que hace idempotente la carga: con
-- INSERT_IGNORE (INSERT ... ON CONFLICT DO NOTHING) las filas repetidas se saltan.
CREATE TABLE eventos (
  estacion_id text,
  tipo_sensor text,
  valor       double precision,
  ts          timestamptz,
  PRIMARY KEY (estacion_id, ts)
);
