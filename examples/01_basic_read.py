"""Example 1: Read GPS data and print to terminal.

Usage:
    python examples/01_basic_read.py
"""
import time
from gps_mouse import GPSReader


def on_data(data):
    if data.has_fix:
        alt     = f"{data.altitude:.1f}m"     if data.altitude  is not None else "---"
        speed   = f"{data.speed_kmh:.1f}km/h" if data.speed_kmh is not None else "---"
        heading = f"{data.heading:.1f}°"       if data.heading   is not None else "---"
        print(
            f"lat={data.latitude:.6f}  "
            f"lon={data.longitude:.6f}  "
            f"alt={alt}  speed={speed}  heading={heading}  "
            f"sats={data.num_satellites}"
        )
    else:
        print(f"[NO FIX] sats={data.num_satellites}")


if __name__ == "__main__":
    with GPSReader() as reader:
        reader.add_callback(on_data)
        print("Reading GPS… Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping.")
