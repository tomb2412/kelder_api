import minimalmodbus
import serial

instrument = minimalmodbus.Instrument('/dev/ttyAMA0', 1)  # Slave address 1
instrument.serial.baudrate = 9600
instrument.serial.bytesize = 8
instrument.serial.parity = serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout = 1
instrument.mode = minimalmodbus.MODE_RTU

try:
    result = instrument.read_register(0x0001, 0, functioncode=3, signed=False)  # Adjust register and decimals
    print("Result:", result)
except Exception as e:
    print("Communication error:", e)

