import time
import board
import busio
from digitalio import Direction
from adafruit_mcp230xx.mcp23017 import MCP23017

i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c, address=0x21)

pins = [13, 10, 15, 14, 7, 3]

for p in pins:
    led = mcp.get_pin(p)
    led.direction = Direction.OUTPUT
    print(f"Testing MCP pin {p}")
    led.value = True
    time.sleep(10)
    led.value = False
    time.sleep(0.3)

print("Done")