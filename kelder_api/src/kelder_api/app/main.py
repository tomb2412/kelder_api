from typing import Union

from fastapi import FastAPI

import serial
import time
import string
import pynmea2

from src.kelder_api.components.health.views import router as health_route
from src.kelder_api.components.gps.views import router as gps_route

app = FastAPI()

app.include_router(health_route)
app.include_router(gps_route)