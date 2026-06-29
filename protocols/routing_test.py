# protocols/routing_test.py

import time


def run(valves):
    print("=== Routing Test ===")

    try:
        print("Loading sample")
        valves.release_all()
        valves.open("sample")
        time.sleep(3)

        print("Switching to wash")
        valves.release_all()
        valves.open("wash")
        time.sleep(3)

        print("Cleaning channel")
        valves.release_all()
        valves.open("waste")
        time.sleep(3)

        print("Routing complete")

    finally:
        print("Returning system to safe state")
        valves.release_all()