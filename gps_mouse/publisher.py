"""ZMQ-based GPS data publisher.

Other processes can connect using GPSSubscriber to receive data.

Architecture:
    GPSReader → GPSPublisher (PUB socket) ← GPSSubscriber (SUB socket)

Default address: tcp://127.0.0.1:5557
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import zmq

from .exceptions import GPSPublisherError
from .models import GPSData

if TYPE_CHECKING:
    from .reader import GPSReader

logger = logging.getLogger(__name__)

DEFAULT_ADDRESS = "tcp://127.0.0.1:5557"


class GPSPublisher:
    """Broadcasts GPS data over a ZMQ PUB socket.

    Usage:
        reader = GPSReader()
        pub = GPSPublisher()
        pub.attach(reader)   # registers as a reader callback automatically
        reader.start()
    """

    def __init__(self, address: str = DEFAULT_ADDRESS) -> None:
        self.address = address
        self._ctx = zmq.Context.instance()
        self._socket: zmq.Socket | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._socket is not None:
            return
        try:
            self._socket = self._ctx.socket(zmq.PUB)
            self._socket.bind(self.address)
            logger.info("GPSPublisher listening: %s", self.address)
        except zmq.ZMQError as e:
            raise GPSPublisherError(f"ZMQ bind error {self.address}: {e}") from e

    def stop(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket = None
        logger.info("GPSPublisher closed.")

    # ------------------------------------------------------------------
    # Attach to reader
    # ------------------------------------------------------------------

    def attach(self, reader: "GPSReader") -> None:
        """Can be called before the reader is started."""
        self.start()
        reader.add_callback(self.publish)

    def detach(self, reader: "GPSReader") -> None:
        reader.remove_callback(self.publish)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, data: GPSData) -> None:
        """Publish a GPSData object as JSON."""
        if self._socket is None:
            self.start()
        try:
            topic = "gps.fix" if data.has_fix else "gps.nofix"
            payload = f"{topic} {data.to_json()}"
            self._socket.send_string(payload, zmq.NOBLOCK)
        except zmq.Again:
            pass  # no subscribers, ignore
        except zmq.ZMQError as e:
            logger.warning("Publish error: %s", e)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "GPSPublisher":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
