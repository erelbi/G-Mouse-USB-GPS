"""Example 3: Receive GPS data from another project (client side).

Requires 02_zmq_server.py to be running.

Usage:
    python examples/03_zmq_client.py
"""
from gps_mouse import GPSSubscriber


if __name__ == "__main__":
    sub = GPSSubscriber()  # tcp://127.0.0.1:5557

    print("Waiting for GPS data… Press Ctrl+C to stop")
    for data in sub.iter_fixes():
        if data.has_fix:
            print(
                f"lat={data.latitude:.6f}  lon={data.longitude:.6f}  "
                f"speed={data.speed_kmh:.1f}km/h  hdop={data.hdop}"
            )
        else:
            print(f"[NO FIX] sats={data.num_satellites}")
