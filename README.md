# gps-mouse 🛰️

[![PyPI version](https://img.shields.io/pypi/v/gps-mouse.svg)](https://pypi.org/project/gps-mouse/)
[![Python](https://img.shields.io/pypi/pyversions/gps-mouse.svg)](https://pypi.org/project/gps-mouse/)
[![Tests](https://github.com/erelbi/G-Mouse-USB-GPS/actions/workflows/tests.yml/badge.svg)](https://github.com/erelbi/G-Mouse-USB-GPS/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight Python library for reading data from U-Blox GPS devices and distributing it to multiple projects via ZMQ, REST API, MQTT, or file logging.

## Features

- Read NMEA sentences (GGA, RMC, VTG) from any serial GPS device
- **Auto-reconnect** when device is unplugged and re-plugged
- **ZMQ pub/sub** — distribute to multiple projects simultaneously
- **REST API + Live map dashboard** — browser-based Leaflet.js map
- **MQTT** — publish to any MQTT broker (Home Assistant, Node-RED, etc.)
- **CSV + GPX logging** — record tracks for later analysis
- **gpsd support** — use the standard Linux GPS daemon
- **CLI tools** — `gps-server`, `gps-read`, `gps-log`, `gps-api`
- **Docker** — single-command deployment
- **Sync and async** support

## Tested Device

| Device | Interface | Default Port |
|---|---|---|
| U-Blox 7 (USB) | `/dev/ttyACM0` | 9600 baud |

Works with any NMEA-compatible GPS device.

---

## Installation

```bash
# Core library
pip install gps-mouse

# With REST API + dashboard
pip install "gps-mouse[api]"

# With MQTT support
pip install "gps-mouse[mqtt]"

# With YAML config support
pip install "gps-mouse[yaml]"

# Everything
pip install "gps-mouse[all]"
```

### System permission (Linux)

```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

---

## Quick Start

### CLI

```bash
# Read and print GPS data
gps-read

# Start server with ZMQ + live map
gps-server --api

# Log to CSV + GPX
gps-log --csv track.csv --gpx track.gpx

# REST API + dashboard only
gps-api
```

### Python — read data

```python
import time
from gps_mouse import GPSReader

def on_data(data):
    if data.has_fix:
        print(f"lat={data.latitude:.6f}  lon={data.longitude:.6f}  alt={data.altitude}m")

with GPSReader() as reader:
    reader.add_callback(on_data)
    time.sleep(60)
```

### Python — ZMQ broadcast + subscribe

```python
# Server (reads GPS, broadcasts)
from gps_mouse import GPSReader, GPSPublisher

reader = GPSReader()
pub = GPSPublisher()
pub.attach(reader)
reader.start()

# Client (any other project)
from gps_mouse import GPSSubscriber

for data in GPSSubscriber().iter_fixes():
    print(data.latitude, data.longitude)
```

### Python — REST API + live map

```python
from gps_mouse import GPSReader
from gps_mouse.api import GPSApi

reader = GPSReader()
reader.start()
GPSApi(reader, port=8080).serve()
# Open http://localhost:8080 in browser
```

### Python — MQTT

```python
from gps_mouse import GPSReader
from gps_mouse.mqtt import GPSMQTTPublisher

reader = GPSReader()
mqtt = GPSMQTTPublisher(broker="localhost", topic="gps/data")
mqtt.attach(reader)
reader.start()
```

### Python — CSV + GPX logging

```python
import time
from gps_mouse import GPSReader
from gps_mouse.logger import GPSLogger

with GPSLogger(csv_path="track.csv", gpx_path="track.gpx") as log:
    with GPSReader() as reader:
        reader.add_callback(log.record)
        time.sleep(3600)
```

### Config file

```bash
cp config.example.yml config.yml
# Edit config.yml
gps-server --config config.yml
```

---

## Docker

```bash
# Start with docker-compose
docker compose up -d

# Open dashboard
open http://localhost:8080
```

---

## systemd Service

```bash
sudo cp systemd/gps-mouse.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gps-mouse
sudo journalctl -u gps-mouse -f
```

---

## Architecture

```
GPS Device (/dev/ttyACM0 or gpsd)
       │
   GPSReader  ─────────────────────────────────────────
       │
       ├──► GPSPublisher (ZMQ PUB :5557)
       │         └─► Project A, B, C (GPSSubscriber)
       │
       ├──► GPSMQTTPublisher → MQTT Broker
       │         └─► Home Assistant, Node-RED, …
       │
       ├──► GPSApi (FastAPI :8080)
       │         ├─► GET /gps        (latest fix JSON)
       │         ├─► GET /gps/stream (SSE stream)
       │         ├─► WS  /gps/ws     (WebSocket)
       │         └─► GET /           (live map)
       │
       └──► GPSLogger → CSV / GPX files
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

---

## Examples

| File | Description |
|---|---|
| `examples/01_basic_read.py` | Print GPS values to terminal |
| `examples/02_zmq_server.py` | Read GPS and broadcast over ZMQ |
| `examples/03_zmq_client.py` | Subscribe from another project |
| `examples/04_async_stream.py` | Async producer/consumer |
| `examples/05_wait_for_fix.py` | Block until first fix |

---

## Requirements

- Python 3.10+
- pyserial, pynmea2, pyzmq *(core)*
- fastapi, uvicorn *(optional — `[api]`)*
- paho-mqtt *(optional — `[mqtt]`)*
- pyyaml *(optional — `[yaml]`)*

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

[MIT](LICENSE) © 2026 erelbi
