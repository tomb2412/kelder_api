from shapely.geometry import shape

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