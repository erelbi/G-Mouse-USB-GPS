"""Configuration loader — supports YAML files and environment variables.

Priority (highest → lowest):
  1. Environment variables  (GPS_PORT, GPS_BAUDRATE, …)
  2. Config file            (config.yml / path passed to load())
  3. Built-in defaults

Usage:
    from gps_mouse.config import Config
    cfg = Config.load("config.yml")
    print(cfg.device.port)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DeviceConfig:
    port: str = "/dev/ttyACM0"
    baudrate: int = 9600
    reconnect: bool = True
    reconnect_delay: float = 5.0


@dataclass
class ZMQConfig:
    enabled: bool = True
    address: str = "tcp://127.0.0.1:5557"


@dataclass
class MQTTConfig:
    enabled: bool = False
    broker: str = "localhost"
    port: int = 1883
    topic: str = "gps/data"
    username: str = ""
    password: str = ""


@dataclass
class APIConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass
class CSVLogConfig:
    enabled: bool = False
    path: str = "gps_log.csv"


@dataclass
class GPXLogConfig:
    enabled: bool = False
    path: str = "gps_track.gpx"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    csv: CSVLogConfig = field(default_factory=CSVLogConfig)
    gpx: GPXLogConfig = field(default_factory=GPXLogConfig)


@dataclass
class Config:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    zmq: ZMQConfig = field(default_factory=ZMQConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        """Load config from YAML file (optional) then apply env overrides."""
        cfg = cls()

        if path:
            cfg._load_yaml(path)

        cfg._apply_env()
        return cfg

    def _load_yaml(self, path: str) -> None:
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for config files: pip install pyyaml"
            )

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        d = data.get("device", {})
        self.device.port = d.get("port", self.device.port)
        self.device.baudrate = int(d.get("baudrate", self.device.baudrate))
        self.device.reconnect = bool(d.get("reconnect", self.device.reconnect))
        self.device.reconnect_delay = float(d.get("reconnect_delay", self.device.reconnect_delay))

        z = data.get("zmq", {})
        self.zmq.enabled = bool(z.get("enabled", self.zmq.enabled))
        self.zmq.address = z.get("address", self.zmq.address)

        m = data.get("mqtt", {})
        self.mqtt.enabled = bool(m.get("enabled", self.mqtt.enabled))
        self.mqtt.broker = m.get("broker", self.mqtt.broker)
        self.mqtt.port = int(m.get("port", self.mqtt.port))
        self.mqtt.topic = m.get("topic", self.mqtt.topic)
        self.mqtt.username = m.get("username", self.mqtt.username)
        self.mqtt.password = m.get("password", self.mqtt.password)

        a = data.get("api", {})
        self.api.enabled = bool(a.get("enabled", self.api.enabled))
        self.api.host = a.get("host", self.api.host)
        self.api.port = int(a.get("port", self.api.port))

        lg = data.get("logging", {})
        self.logging.level = lg.get("level", self.logging.level)
        csv = lg.get("csv", {})
        self.logging.csv.enabled = bool(csv.get("enabled", self.logging.csv.enabled))
        self.logging.csv.path = csv.get("path", self.logging.csv.path)
        gpx = lg.get("gpx", {})
        self.logging.gpx.enabled = bool(gpx.get("enabled", self.logging.gpx.enabled))
        self.logging.gpx.path = gpx.get("path", self.logging.gpx.path)

    def _apply_env(self) -> None:
        """Override with environment variables (GPS_PORT, GPS_BAUDRATE, etc.)."""
        if v := os.getenv("GPS_PORT"):
            self.device.port = v
        if v := os.getenv("GPS_BAUDRATE"):
            self.device.baudrate = int(v)
        if v := os.getenv("GPS_ZMQ_ADDRESS"):
            self.zmq.address = v
        if v := os.getenv("GPS_MQTT_BROKER"):
            self.mqtt.broker = v
        if v := os.getenv("GPS_MQTT_TOPIC"):
            self.mqtt.topic = v
        if v := os.getenv("GPS_API_HOST"):
            self.api.host = v
        if v := os.getenv("GPS_API_PORT"):
            self.api.port = int(v)
