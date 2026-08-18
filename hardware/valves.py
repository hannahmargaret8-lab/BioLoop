# hardware/valves.py

from config.settings import VALVES

try:
    import board
    import busio
    from digitalio import Direction
    from adafruit_mcp230xx.mcp23017 import MCP23017
    HARDWARE = True
except ImportError:
    HARDWARE = False


class ValveController:
    def _resolve_valve(self, valve):
        if isinstance(valve, str):
            return VALVES[valve]
        return valve

    def __init__(self, simulate=False):
        # Force simulation if requested
        if simulate:
            print("ValveController: simulation mode (forced)")
            self.valves = {}
            self._simulate = True
            return

        self._simulate = False

        if HARDWARE:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.mcp = MCP23017(i2c, address=0x21)

            self.valves = {
                1: self.mcp.get_pin(15),
                2: self.mcp.get_pin(14),
                3: self.mcp.get_pin(13),
                4: self.mcp.get_pin(11),
                5: self.mcp.get_pin(10),
                6: self.mcp.get_pin(9),
                7: self.mcp.get_pin(7),
                8: self.mcp.get_pin(6),
                9: self.mcp.get_pin(5),
                10: self.mcp.get_pin(3),
                11: self.mcp.get_pin(2),
                12: self.mcp.get_pin(1),
            }

            for pin in self.valves.values():
                pin.direction = Direction.OUTPUT
                pin.value = False   # safe/off state based on your working test

        else:
            print("Simulation mode: no MCP23017 detected")
            self.valves = {}
            self._simulate = True

    def open(self, valve):
        valve = self._resolve_valve(valve)
        if HARDWARE:
            self.valves[valve].value = True
        else:
            print(f"OPEN valve {valve}")

    def close(self, valve):
        valve = self._resolve_valve(valve)
        if HARDWARE:
            self.valves[valve].value = False
        else:
            print(f"CLOSE valve {valve}")

    def release_all(self):
        for valve in range(1, 13):
            self.close(valve)