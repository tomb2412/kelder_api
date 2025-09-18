# hc_sr04_pi5.py
from time import sleep

from gpiozero import DistanceSensor

# GPIO Pins
TRIG = 23
ECHO = 24


sensor = DistanceSensor(TRIG, ECHO)

while True:
    print("Distance to nearest object is", sensor.distance, "m")
    sleep(0.1)
