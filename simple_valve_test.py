# test_valve.py

import time
import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c, address=0x21)

# Change this to whichever MCP pin you want to test
PIN = 11

valve = mcp.get_pin(PIN)
valve.direction = Direction.OUTPUT

print(f"Testing MCP pin GP{PIN}")

try:
    while True:
        print("ON")
        valve.value = True
        time.sleep(2)

        print("OFF")
        valve.value = False
        time.sleep(2)

except KeyboardInterrupt:
    valve.value = False
    print("Done")