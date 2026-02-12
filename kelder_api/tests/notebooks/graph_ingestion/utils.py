import math

from shapely.geometry import shape

def _parse_wkt_coordinates(
    coordinates: list[list[float, float]]
) -> str:
    coords_string = [f"{lon} {lat}" for lon, lat in coordinates]
    return str(coords_string).replace("[", "").replace("]", "").replace("\"", "").replace("\'", "")


def build_danger_zone_coords(
    coordinates: list[list[float, float]],
    radius_deg: float = 0.0018,
    segments: int = 32,
    cardinal: str | None = None,
) -> str:
    """
    Build a ring WKT coordinate string around a point for Neo4j Spatial.

    Expects coordinates in [lon, lat] order to match current ingestion logic.
    Supports cardinal offsets so the mark touches the ring at a cardinal point.
    """

    if len(coordinates) < 2:
        raise ValueError("coordinates must contain latitude and longitude")
    
    lon = coordinates[0]
    lat = coordinates[1]
    
    center_lat = lat
    center_lon = lon

    if cardinal:
        cardinal = cardinal.lower().strip()
        if cardinal == "north":
            center_lat -= radius_deg*1.05
        elif cardinal == "south":
            center_lat += radius_deg*1.05
        elif cardinal == "east":
            center_lon -= radius_deg*1.05
        elif cardinal == "west":
            center_lon += radius_deg*1.05
        else:
            raise ValueError(f"Unsupported cardinal direction: {cardinal}")

    coords: list[list[float]] = []

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = center_lon + radius_deg * math.cos(angle)
        y = center_lat + radius_deg * math.sin(angle)
        coords.append([x, y])

    # Close the ring
    coords.append(coords[0])

    return _parse_wkt_coordinates(coords)

def process_harbour(feature: dict) -> dict:
    # print(feature)
    try:
        name = feature["properties"]["name"]
    except KeyError:
        name = None
    # get the lat and long
    geometry = shape(feature["geometry"])

    centroid = geometry.centroid
    latitude = centroid.y
    longitude = centroid.x

    try:
        type = feature["properties"]["seamark:harbour:category"]
    except KeyError:
        type = None

    return {"name": name, "type": type, "coordinates": [longitude, latitude]}

def process_fairway(feature: dict) -> dict:
    try:
        name = feature["properties"]["name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    return {"name": name, "type": "fairway", "coordinates": coordinates}

def process_precautionary_area(feature: dict) -> dict:
    try:
        name = feature["properties"]["seamark:name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    return {"name": name, "type": "precautionary_area", "coordinates": coordinates}

def process_lateral_marks(feature: dict, seamark_type: str) -> dict:
    try:
        name = feature["properties"]["seamark:name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    try:
        catagory = feature["properties"][f"seamark:{seamark_type}:category"]
    except KeyError:
        colour = feature["properties"][f"seamark:{seamark_type}:colour"]
        catagory = "port" if colour == "red" else "green"

    try:
        light_character = feature["properties"]["seamark:light:character"]
        light_colour = feature["properties"]["seamark:light:colour"]
        light_group = feature["properties"]["seamark:light:group"]
        light_period = feature["properties"]["seamark:light:period"]

        light_characteristic = f"{light_character}-{light_colour}-group:{light_group}-period:{light_period}"

    except KeyError:
        light_characteristic = None

    return {
        "name": name,
        "type": "lateral_mark",
        "coordinates": coordinates,
        "catagory": catagory,
        "light": light_characteristic,
    }

def process_cardinal_marks(feature: dict, seamark_type: str) -> dict:
    try:
        name = feature["properties"]["seamark:name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    catagory = feature["properties"][f"seamark:{seamark_type}:category"]

    try:
        light_character = feature["properties"]["seamark:light:character"]
        light_colour = feature["properties"]["seamark:light:colour"]
        light_group = feature["properties"]["seamark:light:group"]
        light_period = feature["properties"]["seamark:light:period"]

        light_characteristic = f"{light_character}-{light_colour}-group:{light_group}-period:{light_period}"

    except KeyError:
        light_characteristic = None

    return {
        "name": name,
        "type": "cardinal_mark",
        "coordinates": coordinates,
        "catagory": catagory,
        "light": light_characteristic,
    }

def process_special_purpose(feature: dict) -> dict:
    try:
        name = feature["properties"]["seamark:name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    try:
        light_character = feature["properties"]["seamark:light:character"]
        light_colour = feature["properties"]["seamark:light:colour"]
        light_group = feature["properties"]["seamark:light:group"]
        light_period = feature["properties"]["seamark:light:period"]

        light_characteristic = f"{light_character}-{light_colour}-group:{light_group}-period:{light_period}"

    except KeyError:
        light_characteristic = None

    return {
        "name": name,
        "type": "special_purpose",
        "coordinates": coordinates,
        "light": light_characteristic,
    }

def process_isolated_danger(feature: dict) -> dict:
    try:
        name = feature["properties"]["seamark:name"]
    except KeyError:
        name = None

    coordinates = feature["geometry"]["coordinates"]

    return {"name": name, "type": "isolated_danger", "coordinates": coordinates}

def process_coastline(feature: dict) -> dict:
    try:
        name = feature["properties"]["name"]
    except KeyError:
        name = None

    # island, islet, mainland
    try:
        type = feature["properties"]["place"]
    except KeyError:
        type = 'mainland'

    if feature["geometry"]["type"]=="Polygon":
        coordinates = _parse_wkt_coordinates(feature["geometry"]["coordinates"][0])
    elif feature["geometry"]["type"]=="LineString":
        coordinates = _parse_wkt_coordinates(feature["geometry"]["coordinates"])
    else:
        raise TypeError("Unsupported coordinate WKT type")


    return {"name": name, "type": type, "linestring": coordinates}
    
