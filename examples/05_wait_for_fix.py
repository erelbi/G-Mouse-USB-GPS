"""Example 5: Wait for a fix and read a single position.

Useful for waiting until the GPS is ready in another project.

Usage (requires 02_zmq_server.py to be running):
    python examples/05_wait_for_fix.py
"""
from gps_mouse import GPSSubscriber

if __name__ == "__main__":
    sub = GPSSubscriber()
    print("Waiting for first fix (max 30 seconds)…")
    data = sub.wait_for_fix(timeout=30)

    if data:
        print(f"Fix acquired: {data.latitude:.6f}, {data.longitude:.6f}")
        print(f"Altitude   : {data.altitude} m")
        print(f"Satellites : {data.num_satellites}")
        print(f"HDOP       : {data.hdop}")
    else:
        print("Timeout: no fix acquired.")
