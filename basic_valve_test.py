import time
from hardware.valves import ValveController

valves = ValveController()

try:
    valves.release_all()

    print("sample")
    valves.open("sample")
    time.sleep(2)
    valves.release_all()
    time.sleep(1)

    print("wash")
    valves.open("wash")
    time.sleep(2)
    valves.release_all()
    time.sleep(1)

    print("waste")
    valves.open("waste")
    time.sleep(2)

finally:
    valves.release_all()
    print("safe/off")