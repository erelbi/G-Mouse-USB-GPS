"""Example 2: Read GPS and broadcast over ZMQ (server side).

Other projects can connect using 03_zmq_client.py while this script is running.

Usage:
    python examples/02_zmq_server.py
"""
import time
from gps_mouse import GPSReader, GPSPublisher


if __name__ == "__main__":
    reader = GPSReader()
    pub = GPSPublisher()  # tcp://127.0.0.1:5557

    pub.attach(reader)
    reader.start()

    print(f"GPS broadcast started → {pub.address}")
    print("Press Ctrl+C to stop")

    try:
        while True:
            data = reader.last
            status = f"lat={data.latitude:.6f}, lon={data.longitude:.6f}" if data.has_fix else "NO FIX"
            print(f"\r{status}  sats={data.num_satellites}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        reader.stop()
        pub.stop()
