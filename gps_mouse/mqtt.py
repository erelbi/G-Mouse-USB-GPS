"""MQTT GPS publisher — broadcasts GPS data to an MQTT broker.

Requires: pip install gps-mouse[mqtt]

Usage:
    from gps_mouse import GPSReader
    from gps_mouse.mqtt import GPSMQTTPublisher

    reader = GPSReader()
    mqtt = GPSMQTTPublisher(broker="localhost", topic="gps/data")
    mqtt.attach(reader)
    reader.start()

Subscribing from any MQTT client:
    mosquitto_sub -t gps/data
"""
from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

from .models import GPSData

if TYPE_CHECKING:
    from .reader import GPSReader

logger = logging.getLogger(__name__)


class GPSMQTTPublisher:
    """Publishes GPS data to an MQTT broker.

    Args:
        broker:   MQTT broker hostname
        port:     MQTT broker port (default 1883)
        topic:    MQTT topic (default "gps/data")
        username: Optional broker username
        password: Optional broker password
        qos:      MQTT QoS level 0/1/2
    """

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "gps/data",
        username: str = "",
        password: str = "",
        qos: int = 0,
    ) -> None:
        self.broker = broker
        self.port = port
        self.topic = topic
        self.qos = qos
        self._username = username
        self._password = password
        self._client = None
        self._connected = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise ImportError(
                "paho-mqtt is required: pip install gps-mouse[mqtt]"
            )

        self._client = mqtt.Client()
        if self._username:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        self._client.connect_async(self.broker, self.port)
        self._client.loop_start()
        logger.info("MQTT connecting to %s:%d (topic=%s)", self.broker, self.port, self.topic)

    def stop(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected.clear()
        logger.info("MQTT publisher stopped.")

    # ------------------------------------------------------------------
    # Attach to reader
    # ------------------------------------------------------------------

    def attach(self, reader: "GPSReader") -> None:
        self.start()
        reader.add_callback(self.publish)

    def detach(self, reader: "GPSReader") -> None:
        reader.remove_callback(self.publish)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, data: GPSData) -> None:
        if not self._client or not self._connected.is_set():
            return
        try:
            payload = data.to_json()
            self._client.publish(self.topic, payload, qos=self.qos)
        except Exception as e:
            logger.warning("MQTT publish error: %s", e)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            self._connected.set()
            logger.info("MQTT connected to %s:%d", self.broker, self.port)
        else:
            logger.error("MQTT connection failed (rc=%d)", rc)

    def _on_disconnect(self, client, userdata, rc) -> None:
        self._connected.clear()
        logger.warning("MQTT disconnected (rc=%d)", rc)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "GPSMQTTPublisher":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
