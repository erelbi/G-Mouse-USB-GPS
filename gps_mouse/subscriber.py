"""ZMQ GPS subscriber - for other projects to receive GPS data.

Synchronous usage:
    sub = GPSSubscriber()
    for data in sub.iter_fixes():
        print(data.latitude, data.longitude)

Asynchronous usage:
    async for data in GPSSubscriber().stream():
        print(data)

One-shot usage:
    data = GPSSubscriber().wait_for_fix(timeout=10)
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Iterator

import zmq
import zmq.asyncio

from .exceptions import GPSSubscriberError
from .models import GPSData
from .publisher import DEFAULT_ADDRESS

logger = logging.getLogger(__name__)


class GPSSubscriber:
    """Receives GPS data over ZMQ.

    Args:
        address: Publisher address (default tcp://127.0.0.1:5557)
        topic:   Filter ("gps.fix", "gps.nofix", "gps" → all)
    """

    def __init__(
        self,
        address: str = DEFAULT_ADDRESS,
        topic: str = "gps",
    ) -> None:
        self.address = address
        self.topic = topic

    # ------------------------------------------------------------------
    # Synchronous interface
    # ------------------------------------------------------------------

    def iter_fixes(self, timeout_ms: int = 5000) -> Iterator[GPSData]:
        """Synchronous generator: yields GPSData for every incoming reading."""
        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(self.address)
        sock.setsockopt_string(zmq.SUBSCRIBE, self.topic)
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        logger.info("GPSSubscriber connected: %s (topic=%s)", self.address, self.topic)
        try:
            while True:
                try:
                    msg = sock.recv_string()
                    data = self._parse_message(msg)
                    if data:
                        yield data
                except zmq.Again:
                    logger.debug("Timeout — waiting for data…")
        finally:
            sock.close()

    def wait_for_fix(self, timeout: float = 10.0) -> GPSData | None:
        """Wait for the first fix and return it. Returns None on timeout."""
        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(self.address)
        sock.setsockopt_string(zmq.SUBSCRIBE, "gps.fix")
        sock.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
        try:
            msg = sock.recv_string()
            return self._parse_message(msg)
        except zmq.Again:
            return None
        finally:
            sock.close()

    # ------------------------------------------------------------------
    # Asynchronous interface
    # ------------------------------------------------------------------

    async def stream(self) -> AsyncIterator[GPSData]:
        """Async generator: use as `async for data in sub.stream()`."""
        ctx = zmq.asyncio.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(self.address)
        sock.setsockopt_string(zmq.SUBSCRIBE, self.topic)
        logger.info("GPSSubscriber (async) connected: %s", self.address)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(sock.recv_string(), timeout=5.0)
                    data = self._parse_message(msg)
                    if data:
                        yield data
                except asyncio.TimeoutError:
                    logger.debug("Async timeout — waiting…")
        finally:
            sock.close()

    async def wait_for_fix_async(self, timeout: float = 10.0) -> GPSData | None:
        """Async: wait for the first fix and return it."""
        ctx = zmq.asyncio.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(self.address)
        sock.setsockopt_string(zmq.SUBSCRIBE, "gps.fix")
        try:
            msg = await asyncio.wait_for(sock.recv_string(), timeout=timeout)
            return self._parse_message(msg)
        except asyncio.TimeoutError:
            return None
        finally:
            sock.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_message(msg: str) -> GPSData | None:
        try:
            _, json_part = msg.split(" ", 1)
            return GPSData.from_json(json_part)
        except Exception as e:
            logger.warning("Failed to parse message: %s — %s", msg[:60], e)
            return None
