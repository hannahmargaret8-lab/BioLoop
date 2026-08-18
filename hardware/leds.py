import time

try:
    import board
    import busio
    from digitalio import Direction
    from adafruit_mcp230xx.mcp23017 import MCP23017

    HARDWARE = True

except ImportError:
    HARDWARE = False


class LEDController:
    def __init__(self, simulate=False):
        if simulate:
            print("LEDController: simulation mode (forced)")
            self.salinity_leds = {}
            self.fault_red = None
            self._simulate = True
            return

        self._simulate = False

        if HARDWARE:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.mcp = MCP23017(i2c, address=0x21)

            # Placeholder pins — update after wiring/testing
            self.salinity_leds = {
                "red": self.mcp.get_pin(13),
                "yellow": self.mcp.get_pin(10),
                "green": self.mcp.get_pin(15),
                "blue": self.mcp.get_pin(14),
                "white": self.mcp.get_pin(7),
            }

            self.fault_red = self.mcp.get_pin(3)

            for led in list(self.salinity_leds.values()) + [self.fault_red]:
                led.direction = Direction.OUTPUT

        else:
            print("LED simulation mode")
            self.salinity_leds = {}
            self.fault_red = None
            self._simulate = True

    def salinity_off(self):
        if HARDWARE:
            for led in self.salinity_leds.values():
                led.value = False
        else:
            print("SALINITY LEDs OFF")

    def show_salinity(self, color):
        self.salinity_off()

        if HARDWARE:
            self.salinity_leds[color].value = True
        else:
            print(f"SALINITY LED: {color.upper()}")

    def fault_off(self):
        if HARDWARE:
            self.fault_red.value = False
        else:
            print("FAULT RED LED: OFF")

    def fault_solid(self):
        if HARDWARE:
            self.fault_red.value = True
        else:
            print("FAULT RED LED: SOLID")

    def fault_blink(self, speed="slow", n=5):
        delay = 0.8 if speed == "slow" else 0.2

        for _ in range(n):
            if HARDWARE:
                self.fault_red.value = True
            else:
                print("FAULT RED LED: ON")

            time.sleep(delay)

            if HARDWARE:
                self.fault_red.value = False
            else:
                print("FAULT RED LED: OFF")

            time.sleep(delay)

    def show_fault(self, fault):
        state = fault["fault_led"]

        if state == "off":
            self.fault_off()
        elif state == "solid":
            self.fault_solid()
        elif state == "slow_blink":
            self.fault_blink(speed="slow")
        elif state == "fast_blink":
            self.fault_blink(speed="fast")
        elif state == "pulse":
            self.fault_blink(speed="slow", n=2)