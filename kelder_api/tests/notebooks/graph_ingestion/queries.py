ADD_NATIVE_LAYER = """CALL spatial.addNativePointLayer($layer_name)"""
ADD_DANGER_LAYERS = """CALL spatial.addLayer($layer_name, 'wkt', 'danger_zone');"""

CREATE_DANGER_MARK = """
// 1) Create danger mark (POINT)
CREATE (dm:Mark {
    name: $name,
    type: 'DANGER',
    light: 'Fl(2) W',
    latitude: $coordinates[1],
    longitude: $coordinates[0]
})
SET dm.location = point(dm)

WITH dm

CALL spatial.addNodes($point_layer, [dm])
YIELD count AS pointCount

CREATE (dz:dangerZone {
    name: $name,
    type: 'DANGER',
    danger_zone: 'POLYGON((' + $danger_zone + '))'
})

WITH dm, dz, pointCount

CALL spatial.addNodes($danger_layer, [dz])
YIELD count AS polygonCount

RETURN
  pointCount,
  polygonCount
"""

CREATE_SPECIAL_PURPOSE_MARK = """
CREATE (n:Mark {
    name: $name,
    type: $type,
    light: $light,
    latitude: $coordinates[1],
    longitude: $coordinates[0]
})
SET
    n.location=point(n)
WITH n AS node
CALL spatial.addNodes($layer_name, [node])
YIELD count
RETURN count;
"""

CREATE_GENERAL_MARK_BATCH = """
UNWIND $marks AS m
CREATE (n:Mark)
SET
    n.name = m.name,
    n.type = m.type,
    n.category = m.category,
    n.light = m.light,
    'POINT(' + toString($coordinates[1]) + ' ' + toString($coordinates[0]) + ')'
    n.geom = POINT(' + toString(m.coordinates[1]) + ' ' + toString(m.coordinates[0]) + ')
WITH collect(n) AS nodes
CALL spatial.addNodes($layer_name, nodes)
YIELD count
RETURN count;
"""

DELETE_ALL_NODES = """
MATCH (n) DETACH DELETE n
"""

CREATE_SAFE_EDGES = """
MATCH (m1:Mark)
CALL spatial.withinDistance(
    'solent_marks',
    m1,
    $max_distance_km
)
YIELD node AS m2, distance
WHERE m2:Mark AND m1 <> m2
WITH m1, m2, distance,
    'LINESTRING(' + toString(m1.longitude) + ' ' + toString(m1.latitude) + ', ' +
        toString(m2.longitude) + ' ' + toString(m2.latitude) +
    ')' AS edgeWkt
WHERE NOT EXISTS {
    CALL spatial.intersects('danger_zones', edgeWkt)
    YIELD node as d
    WITH d
    WHERE d.type = 'DANGER'
      AND d.danger_zone IS NOT NULL
    RETURN d
  }
MERGE (m1)-[:SAFE_EDGE]->(m2)
RETURN 
    m1.name as from,
    m2.name as to,
    distance as distanceKm
"""