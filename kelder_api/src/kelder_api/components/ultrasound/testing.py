# hc_sr04_pi5.py
from gpiozero import DistanceSensor
from time import sleep

# GPIO Pins
TRIG = 23
ECHO = 24


sensor = DistanceSensor(23, 24)

while True:
    print('Distance to nearest object is', sensor.distance, 'm')
    sleep(0.1)    