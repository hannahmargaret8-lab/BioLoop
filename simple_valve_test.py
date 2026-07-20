# test_valve.py

import time
import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c, address=0x21)

# Pins to test one at a time
TEST_PINS = [2, 5]

# Pins that stay ON continuously
ALWAYS_ON_PINS = [7]

# Configure always-on pins
always_on = []
for pin in ALWAYS_ON_PINS:
    p = mcp.get_pin(pin)
    p.direction = Direction.OUTPUT
    p.value = True
    always_on.append(p)

# Configure test pins
test_pins = {}
for pin in TEST_PINS:
    p = mcp.get_pin(pin)
    p.direction = Direction.OUTPUT
    p.value = False
    test_pins[pin] = p

print(f"Sequentially testing MCP pins {TEST_PINS}")
print(f"Keeping MCP pins {ALWAYS_ON_PINS} ON")

try:
    while True:

        # -------------------------
        # Pin 2
        # -------------------------
        print("PIN 2 ON")
        test_pins[2].value = True
        test_pins[5].value = False
        time.sleep(3)

        print("ALL TEST PINS OFF")
        test_pins[2].value = False
        test_pins[5].value = False
        time.sleep(2)

        # -------------------------
        # Pin 5
        # -------------------------
        print("PIN 5 ON")
        test_pins[2].value = False
        test_pins[5].value = True
        time.sleep(3)

        print("ALL TEST PINS OFF")
        test_pins[2].value = False
        test_pins[5].value = False
        time.sleep(10)

except KeyboardInterrupt:

    # Turn test valves off
    for p in test_pins.values():
        p.value = False

    # Leave always-on valves energized
    for p in always_on:
        p.value = True

    print("Done")