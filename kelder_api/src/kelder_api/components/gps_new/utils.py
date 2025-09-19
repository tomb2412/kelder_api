def round_ddmm(value: str, deg_digits: int = 2) -> str:
    """
    Rounds a DDMM.MMMM or DDDMM.MMMM string to 2 decimals in the minutes part.
    deg_digits = 2 for latitude, 3 for longitude
    """
    if not isinstance(value, str):
        raise TypeError("Coordinate must be a string in DDMM.MMMM format")
    try:
        deg = value[:deg_digits]
        minutes = float(value[deg_digits:])
    except Exception as e:
        raise ValueError(f"Invalid coordinate format: {value}") from e

    minutes_rounded = round(minutes, 2)
    return f"{deg}{minutes_rounded:05.2f}"
