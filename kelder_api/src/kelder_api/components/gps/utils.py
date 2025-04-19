def nmea_to_dms(nmea_val, is_latitude=True):
    if is_latitude:
        degrees = int(nmea_val // 100)
        minutes_full = nmea_val - (degrees * 100)
    else:
        degrees = int(nmea_val // 100)
        minutes_full = nmea_val - (degrees * 100)

    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60

    return "%+03d°%02d′%04.2f″" % (degrees, minutes, seconds)
