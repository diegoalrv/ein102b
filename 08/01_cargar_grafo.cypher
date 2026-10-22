// Laboratorio 08 — Red sintética de paradas del Gran Concepción.
// 12 paradas · 7 comunas · 4 líneas. Coordenadas aproximadas, solo para el ejercicio.
// Modelo:
//   (:Parada {id, nombre, lat, lon})-[:EN]->(:Comuna {nombre})
//   (:Linea {id, nombre})-[:PASA_POR {orden}]->(:Parada)
//   (:Parada)-[:SIGUE_A {linea, minutos}]->(:Parada)     // en el sentido de la línea
// Se carga UNA vez: si se repite, los CREATE chocan con las restricciones de unicidad (a propósito).
// Esperado: Comuna 7 · Linea 4 · Parada 12 · EN 12 · PASA_POR 16 · SIGUE_A 12

CREATE CONSTRAINT parada_id IF NOT EXISTS FOR (p:Parada) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT comuna_nombre IF NOT EXISTS FOR (c:Comuna) REQUIRE c.nombre IS UNIQUE;
CREATE CONSTRAINT linea_id IF NOT EXISTS FOR (l:Linea) REQUIRE l.id IS UNIQUE;

UNWIND ['Concepción','Talcahuano','Hualpén','San Pedro de la Paz',
        'Chiguayante','Penco','Coronel'] AS nombre
CREATE (:Comuna {nombre: nombre});

UNWIND [
  {id:'P01', nombre:'Plaza Perú',                comuna:'Concepción',          lat:-36.8270, lon:-73.0498},
  {id:'P02', nombre:'Universidad de Concepción', comuna:'Concepción',          lat:-36.8281, lon:-73.0356},
  {id:'P03', nombre:'Terminal Collao',           comuna:'Concepción',          lat:-36.8055, lon:-73.0300},
  {id:'P04', nombre:'Barrio Norte',              comuna:'Concepción',          lat:-36.8040, lon:-73.0420},
  {id:'P05', nombre:'Puente Llacolén',           comuna:'San Pedro de la Paz', lat:-36.8350, lon:-73.0690},
  {id:'P06', nombre:'Mall del Trébol',           comuna:'Talcahuano',          lat:-36.7880, lon:-73.0750},
  {id:'P07', nombre:'Terminal Talcahuano',       comuna:'Talcahuano',          lat:-36.7240, lon:-73.1170},
  {id:'P08', nombre:'Parque Pedro del Río',      comuna:'Hualpén',             lat:-36.7950, lon:-73.1050},
  {id:'P09', nombre:'Plaza Chiguayante',         comuna:'Chiguayante',         lat:-36.9210, lon:-73.0280},
  {id:'P10', nombre:'Plaza Penco',               comuna:'Penco',               lat:-36.7380, lon:-72.9970},
  {id:'P11', nombre:'Plaza Coronel',             comuna:'Coronel',             lat:-37.0300, lon:-73.1400},
  {id:'P12', nombre:'Lomas Coloradas',           comuna:'San Pedro de la Paz', lat:-36.8700, lon:-73.1000}
] AS r
MATCH (c:Comuna {nombre: r.comuna})
CREATE (p:Parada {id: r.id, nombre: r.nombre, lat: r.lat, lon: r.lon})
CREATE (p)-[:EN]->(c);

UNWIND [
  {id:'L1', nombre:'Concepción–Talcahuano',  paradas:['P01','P06','P08','P07'], minutos:[12,8,10]},
  {id:'L2', nombre:'Concepción–Penco',       paradas:['P02','P01','P04','P10'], minutos:[6,7,18]},
  {id:'L3', nombre:'Collao–Lomas Coloradas', paradas:['P03','P02','P09','P12'], minutos:[9,15,14]},
  {id:'L4', nombre:'Concepción–Coronel',     paradas:['P01','P05','P12','P11'], minutos:[9,11,20]}
] AS l
CREATE (li:Linea {id: l.id, nombre: l.nombre})
WITH li, l
UNWIND range(0, size(l.paradas) - 1) AS i
MATCH (p:Parada {id: l.paradas[i]})
CREATE (li)-[:PASA_POR {orden: i + 1}]->(p)
WITH l, i
WHERE i < size(l.paradas) - 1
MATCH (a:Parada {id: l.paradas[i]}), (b:Parada {id: l.paradas[i + 1]})
CREATE (a)-[:SIGUE_A {linea: l.id, minutos: l.minutos[i]}]->(b);
