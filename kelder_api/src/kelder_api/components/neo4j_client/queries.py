ADD_NATIVE_LAYER = """CALL spatial.addNativePointLayer($layer_name)"""
ADD_DANGER_LAYER = """CALL spatial.addLayer($layer_name, 'wkt', 'danger_zone')"""
ADD_COASTLINE_LAYER = """CALL spatial.addLayer($layer_name, 'wkt', 'coastline')"""

DELETE_ALL_NODES = """MATCH (n) DETACH DELETE n"""

CHECK_GRAPH_EXISTS = """
CALL gds.graph.exists($graph_name) YIELD exists
"""

DROP_GRAPH_IF_EXISTS = """
CALL gds.graph.drop($graph_name, false)
YIELD graphName
RETURN graphName
"""

CREATE_GRAPH = """
CALL gds.graph.project(
  $graph_name,
  {Mark: {properties: ['latitude', 'longitude']}},
  {SAFE_EDGE: {type: 'SAFE_EDGE', orientation: 'UNDIRECTED', properties: 'distance_km'}}
)
YIELD graphName
RETURN graphName
"""

CREATE_GENERAL_MARK = """
CREATE (n:Mark {
    name: $name,
    type: $type,
    light: $light,
    latitude: $coordinates[1],
    longitude: $coordinates[0]
})
SET n.location = point({longitude: n.longitude, latitude: n.latitude})
WITH n AS node
CALL spatial.addNodes($layer_name, [node])
YIELD count
RETURN count
"""

CREATE_DANGER_MARK = """
CREATE (mark:Mark {
    name: $name,
    type: $type,
    light: $light,
    latitude: $coordinates[1],
    longitude: $coordinates[0]
})
SET mark.location = point({longitude: mark.longitude, latitude: mark.latitude})
WITH mark
CALL spatial.addNodes($point_layer, [mark])
YIELD count AS point_count
CREATE (zone:DangerZone {
    name: $name,
    type: $type,
    danger_zone: 'POLYGON((' + $danger_zone + '))'
})
WITH zone, point_count
CALL spatial.addNodes($danger_layer, [zone])
YIELD count AS polygon_count
RETURN point_count, polygon_count
"""

CREATE_COASTLINE = """
CREATE (coastline:Coastline {
    name: $name,
    type: $type,
    coastline: 'LINESTRING(' + $linestring + ')'
})
WITH coastline
CALL spatial.addNodes($coastline_layer, [coastline])
YIELD count as coastline_count
RETURN coastline_count
"""

CREATE_HARBOUR = """
CREATE (n:Mark {
    name: $name,
    type: 'HARBOUR',
    category: $category,
    latitude: $coordinates[1],
    longitude: $coordinates[0]
})
SET n.location = point({longitude: n.longitude, latitude: n.latitude})
WITH n AS node
CALL spatial.addNodes($layer_name, [node])
YIELD count
RETURN count
"""

CREATE_SAFE_EDGES = """
MATCH (m1:Mark)
CALL spatial.withinDistance($point_layer, m1, $max_distance_km)
YIELD node AS m2, distance
WHERE m2:Mark AND m1 <> m2
WITH m1, m2, distance,
    'LINESTRING(' + toString(m1.longitude) + ' ' + toString(m1.latitude) + ', ' +
    toString(m2.longitude) + ' ' + toString(m2.latitude) + ')' AS edge_wkt
WHERE NOT EXISTS {
    WITH edge_wkt
    CALL spatial.intersects($danger_layer, edge_wkt)
    YIELD node
    RETURN node LIMIT 1
}
AND NOT EXISTS {
    WITH edge_wkt
    CALL spatial.intersects($coastline_layer, edge_wkt)
    YIELD node
    RETURN node LIMIT 1
}
MERGE (m1)-[r:SAFE_EDGE]->(m2)
SET r.distance_km = distance
RETURN m1.name AS from_name, m2.name AS to_name, r.distance_km AS distance_km
"""

A_STAR_ROUTE_OPTIMISATION_WITH_NAMES = """
MATCH (source:Mark {name: $name_from}), (target:Mark {name: $name_to})
CALL gds.shortestPath.astar.stream($gds_graph, {
    sourceNode: source,
    targetNode: target,
    latitudeProperty: 'latitude',
    longitudeProperty: 'longitude',
    relationshipWeightProperty: 'distance_km'
})
YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path
RETURN
    index,
    gds.util.asNode(sourceNode).name AS sourceNodeName,
    gds.util.asNode(targetNode).name AS targetNodeName,
    totalCost,
    [nodeId IN nodeIds | gds.util.asNode(nodeId).name] AS nodeNames,
    costs,
    nodes(path) as path
ORDER BY index
"""
