import time
import redis

from src.kelder_api.components.gps.service import SerialConnection, getGpCoords

HIGH_FREQ = 1 # Seconds between samples
LOW_FREQ = 30 
VELOCITY_THRESHOLD = 1.5 # speed exceeds 1.5 kts 

r = redis.Redis(host='localhost', port=6379, db=0)

async def initiate_sensing():
    sleep_interval = HIGH_FREQ

    serial_reader = await SerialConnection()

    while True:
        timestamped_gps = await getGpCoords(serial_reader)
        
        r.set('gps:Latest',f)
        r.lpush('gps:Histroy', )
