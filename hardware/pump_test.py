from protocols.biofilm_dc_pump import DSCMPump

pump = DSCMPump(port="/dev/ttyACM0")
pump.connect()
pump.stop()
pump.set_flow_rate(5)
pump.start()
time.sleep(30)
pump.stop()
pump.close()