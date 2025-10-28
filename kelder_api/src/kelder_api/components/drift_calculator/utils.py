def bearing_angle_difference(bearing_1, bearing_2):
    """
    Returns the smallest angle between two bearings in degrees.
    Bearings should be given in degrees (0–360).
    """
    diff = abs(bearing_1 - bearing_2) % 360
    return min(diff, 360 - diff)