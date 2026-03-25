# gps-mouse 🛰️

A lightweight Python library for reading data from U-Blox GPS devices and distributing it to multiple projects via ZMQ pub/sub.

## Features

- Reads NMEA sentences (GGA, RMC, VTG) from any serial GPS device
- Parses latitude, longitude, altitude, speed, heading, satellite count, HDOP
- Distributes data via **callbacks** (in-process) or **ZMQ pub/sub** (inter-process)
- Supports both **synchronous** and **async/await** usage
- Built-in speed noise filter for stationary readings
- Context manager support

## Tested Device

| Device | Interface | Default Port |
|---|---|---|
| U-Blox 7 (USB) | `/dev/ttyACM0` | 9600 baud |

Works with any NMEA-compatible GPS device.

---

## Installation

```bash
pip install gps-mouse
```

Or install from source:

```bash
git clone https://github.com/YOUR_USERNAME/gps-mouse.git
cd gps-mouse
pip install -e .
```

### System permission

The GPS device requires `dialout` group access on Linux:

```bash
sudo usermod -aG dialout $USER
# Re-login or run: newgrp dialout
```

---

## Quick Start

### Read and print GPS data

```python
import time
from gps_mouse import GPSReader

def on_data(data):
    if data.has_fix:
        print(f"lat={data.latitude:.6f}  lon={data.longitude:.6f}  alt={data.altitude}m")
    else:
        print(f"[NO FIX] sats={data.num_satellites}")

with GPSReader() as reader:
    reader.add_callback(on_data)
    time.sleep(60)
```

### Broadcast to other projects (ZMQ)

**Server** — reads GPS and broadcasts:
```python
from gps_mouse import GPSReader, GPSPublisher

reader = GPSReader()
pub = GPSPublisher()
pub.attach(reader)
reader.start()
```

**Client** — any other project subscribes:
```python
from gps_mouse import GPSSubscriber

for data in GPSSubscriber().iter_fixes():
    print(data.latitude, data.longitude)
```

### Async usage

```python
import asyncio
from gps_mouse import GPSReader

async def main():
    async for data in GPSReader().stream():
        print(data)

asyncio.run(main())
```

### Wait for first fix

```python
from gps_mouse import GPSSubscriber

data = GPSSubscriber().wait_for_fix(timeout=30)
if data:
    print(f"{data.latitude:.6f}, {data.longitude:.6f}")
```

---

## GPSData Fields

| Field | Type | Description |
|---|---|---|
| `latitude` | `float \| None` | Decimal degrees (negative = South) |
| `longitude` | `float \| None` | Decimal degrees (negative = West) |
| `altitude` | `float \| None` | Metres above mean sea level |
| `speed` | `float \| None` | Speed in m/s |
| `speed_kmh` | `float \| None` | Speed in km/h (property) |
| `heading` | `float \| None` | True North heading in degrees |
| `fix_quality` | `FixQuality` | GPS fix type (NO_FIX, GPS, DGPS, RTK…) |
| `num_satellites` | `int` | Number of satellites in use |
| `hdop` | `float \| None` | Horizontal dilution of precision |
| `timestamp` | `datetime` | UTC timestamp from device |
| `has_fix` | `bool` | True if a valid position fix exists |

### Serialization

```python
data.to_dict()   # → Python dict
data.to_json()   # → JSON string

GPSData.from_json(json_str)   # deserialize
GPSData.from_dict(d)
```

---

## Architecture

```
GPS Device (/dev/ttyACM0)
       │
   GPSReader  ──callback──▶  GPSPublisher (ZMQ PUB :5557)
                                    │
                          ┌─────────┼─────────┐
                       Project A  Project B  Project C
                      (GPSSubscriber)
```

---

## Examples

| File | Description |
|---|---|
| `examples/01_basic_read.py` | Print GPS values to terminal |
| `examples/02_zmq_server.py` | Read GPS and broadcast over ZMQ |
| `examples/03_zmq_client.py` | Subscribe to GPS from another project |
| `examples/04_async_stream.py` | Async producer/consumer pattern |
| `examples/05_wait_for_fix.py` | Block until first fix is acquired |

---

## Requirements

- Python 3.10+
- pyserial
- pynmea2
- pyzmq

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

---

## License

[MIT](LICENSE) © 2026 ebilsel
