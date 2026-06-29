# test_8_valves.py

import time
import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c, address=0x21)

# GP pins corresponding to valves 1-7
pins = [5, 6, 7, 9, 11, 1, 2]

valves = []

for p in pins:
    pin = mcp.get_pin(p)
    pin.direction = Direction.OUTPUT
    valves.append(pin)

try:
    while True:
        print("Opening all 8 valves")

        # Active LOW (change to True if your hardware is active HIGH)
        for v in valves:
            v.value = False

        time.sleep(5)

        print("Closing all 8 valves")

        for v in valves:
            v.value = True

        time.sleep(5)

except KeyboardInterrupt:
    print("Returning valves to safe state")
    for v in valves:
        v.value = True