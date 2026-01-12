CREATE_DANGER_MARK = """
CREATE (d:Mark)
SET 
    d.name: $name,
    d.type = 'DANGER',
    d.light = 'Fl(2) W',
    d.geom = 'POINT(' + toString(d.coordinates[0]) + ' ' + toString(d.coordinates[1]) + ')'
    d.dangerZone = spatial.asGeometry($danger_zone)
WITH d as danger_mark
CALL spatial.addNodes($layer_name, danger_mark)
YIELD NODE
RETURN NODE;
"""

CREATE_GENERAL_MARK_BATCH = """
UNWIND $marks AS m
CREATE (n:Mark)
SET
    n.name = m.name,
    n.type = m.type,
    n.category = m.category,
    n.light = m.light,
    n.geom = 'POINT(' + toString(m.coordinates[0]) + ' ' + toString(m.coordinates[1]) + ')'
WITH collect(n) AS nodes
CALL spatial.addNodes($layer_name, nodes)
YIELD count
RETURN count;
"""

DELETE_ALL_NODES = """
MATCH (n) DETACH DELETE n
"""
