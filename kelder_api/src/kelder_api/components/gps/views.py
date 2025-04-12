from fastapi import APIRouter

router = APIRouter()

@router.get("/gps_coords")
def get_gps_coords():
    port="/dev/ttyAMA0"
    ser=serial.Serial(port, baudrate=9600, timeout=0.5)
    dataout = pynmea2.NMEAStreamReader()
    newdata=ser.readline()

    if newdata[0:6] == "$GPRMC":
        newmsg=pynmea2.parse(newdata)
        lat=newmsg.latitude
        lng=newmsg.longitude
        gps = "Latitude=" + str(lat) + "and Longitude=" + str(lng)

        return {"Latitude":  str(lat), "Longitude": str(lng)}
    
    else:
        return {}