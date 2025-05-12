import board
import math as m
import time
import adafruit_lsm303_accel
import adafruit_lis2mdl

i2c = board.I2C()
accel = adafruit_lsm303_accel.LSM303_Accel(i2c)
magnetometer = adafruit_lis2mdl.LIS2MDL(i2c)

print("Acceleration (m/s^2): X=%0.3f Y=%0.3f Z=%0.3f" % accel.acceleration)
print("Magnetometer (micro-Teslas)): X=%0.3f Y=%0.3f Z=%0.3f" % magnetometer.magnetic)

while True:
    mag_x, mag_y, mag_z = magnetometer.magnetic
    magnitude = m.sqrt(mag_x**2 + mag_y**2 + mag_z**2)

    norm_x = mag_x / magnitude
    norm_y = mag_y / magnitude
    norm_z = mag_z / magnitude

    heading = m.atan2(norm_y, norm_x)
    heading_degrees = m.degrees(heading)

    if heading < 0:
        heading += 360

    print(f"Heading: {heading_degrees:.2f}°")
    time.sleep(0.2)
