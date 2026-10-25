def sign_ddmm(value: str | None, negative: bool) -> str | None:
    """
    Applies the hemisphere to an unsigned NMEA DDMM.MMMM / DDDMM.MMMM string.
    Coordinates are stored signed (negative = South / West), matching the simulator,
    so downstream code doesn't need the separate N/S/E/W field.
    """
    if not value or not negative or value.startswith("-"):
        return value
    return f"-{value}"


def round_ddmm(value: str, deg_digits: int = 2) -> str:
    """
    Rounds a (optionally signed) DDMM.MMMM or DDDMM.MMMM string to 2 decimals in the
    minutes part, carrying into the degrees if the minutes round up to 60.
    deg_digits = 2 for latitude, 3 for longitude (zero-padded width of the output)
    """
    if value == "":
        return ""
    if not isinstance(value, str):
        raise TypeError("Coordinate must be a string in DDMM.MMMM format")

    sign = "-" if value.startswith("-") else ""
    whole, _, frac = value.lstrip("+-").partition(".")
    if len(whole) < 2 or not whole.isdigit() or (frac and not frac.isdigit()):
        raise ValueError(f"Invalid coordinate format: {value}")

    # Minutes are the two digits before the decimal point, whatever the degree width
    degrees = int(whole[:-2] or "0")
    minutes_rounded = round(float(f"{whole[-2:]}.{frac or '0'}"), 2)
    if minutes_rounded >= 60:
        degrees += 1
        minutes_rounded -= 60

    return f"{sign}{degrees:0{deg_digits}d}{minutes_rounded:05.2f}"
