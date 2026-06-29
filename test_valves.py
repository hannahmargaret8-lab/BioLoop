# test_valves.py

import time
from hardware.valves import ValveController


valves = ValveController()


try:
    print("=== Valve Test ===")

    print("Testing sample valve")
    valves.open("sample")
    time.sleep(2)

    valves.release_all()
    time.sleep(2)


    print("Testing wash valve")
    valves.open("wash")
    time.sleep(2)

    valves.release_all()
    time.sleep(2)


    print("Testing waste valve")
    valves.open("waste")
    time.sleep(2)


finally:
    print("Returning valves to safe state")
    valves.release_all()


print("Valve test complete")