# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3] — 2026-03-25

### Fixed
- PyPI publish workflow: removed `environment` requirement, added explicit `user: __token__`

## [0.1.1] — 2026-03-25

### Added
- **Auto-reconnect**: GPSReader automatically reconnects when USB device is unplugged and re-plugged
- **Config file**: YAML configuration support (`config.example.yml`)
- **CSV + GPX logger**: Record GPS tracks to file (`GPSLogger`)
- **MQTT publisher**: Broadcast GPS data to any MQTT broker (`GPSMQTTPublisher`)
- **REST API + Live map dashboard**: FastAPI server with WebSocket streaming and Leaflet.js map (`GPSApi`)
- **gpsd support**: Alternative reader using gpsd daemon (`GPSDReader`)
- **CLI commands**: `gps-server`, `gps-read`, `gps-log`, `gps-api`
- **Docker support**: `Dockerfile` and `docker-compose.yml`
- **systemd service**: `systemd/gps-mouse.service`
- Optional dependency groups: `[api]`, `[mqtt]`, `[yaml]`, `[all]`

### Fixed
- South/West hemisphere coordinate sign bug (double negation in pynmea2 parsing)
- `gps_qual` None guard for no-fix GGA sentences

## [0.1.0] — 2026-03-25

### Added
- Initial release
- `GPSReader`: serial NMEA reader (GGA, RMC, VTG) with callback and async stream support
- `GPSPublisher`: ZMQ PUB socket broadcaster
- `GPSSubscriber`: ZMQ SUB socket client for other projects
- `GPSData`: dataclass with JSON serialization
- `FixQuality` enum
- 83 unit tests
- MIT license
