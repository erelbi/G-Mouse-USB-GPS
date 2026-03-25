"""gpsd protocol reader — alternative to direct serial access.

Uses the standard gpsd daemon instead of reading the serial port directly.
Useful when gpsd is already running on the system.

Requires gpsd to be running:
    sudo apt install gpsd
    sudo gpsd /dev/ttyACM0 -F /var/run/gpsd.sock

Usage:
    from gps_mouse.gpsd import GPSDReader

    reader = GPSDReader()
    reader.add_callback(lambda d: print(d))
    reader.start()
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from datetime import datetime, timezone
from typing import AsyncIterator, Callable

from .models import FixQuality, GPSData
from .exceptions import GPSDeviceNotFound

logger = logging.getLogger(__name__)

GPSCallback = Callable[[GPSData], None]

_WATCH_CMD = b'?WATCH={"enable":true,"json":true}\n'


class GPSDReader:
    """Reads from a running gpsd daemon via TCP.

    Args:
        host: gpsd host (default localhost)
        port: gpsd port (default 2947)
        reconnect: auto-reconnect on disconnect
        reconnect_delay: seconds between reconnect attempts
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2947,
        reconnect: bool = True,
        reconnect_delay: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay

        self._callbacks: list[GPSCallback] = []
        self._queues: list[asyncio.Queue[GPSData]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_data = GPSData(timestamp=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def add_callback(self, cb: GPSCallback) -> None:
        self._callbacks.append(cb)

    def remove_callback(self, cb: GPSCallback) -> None:
        self._callbacks.remove(cb)

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="gpsd-reader")
        self._thread.start()
        logger.info("GPSDReader started: %s:%d", self.host, self.port)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("GPSDReader stopped.")

    async def stream(self, maxsize: int = 100) -> AsyncIterator[GPSData]:
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue[GPSData] = asyncio.Queue(maxsize=maxsize)
        self._queues.append(q)
        self.start()
        try:
            while True:
                data = await q.get()
                yield data
        finally:
            self._queues.remove(q)

    @property
    def last(self) -> GPSData:
        return self._last_data

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=5) as sock:
                    sock.sendall(_WATCH_CMD)
                    buf = ""
                    while not self._stop_event.is_set():
                        chunk = sock.recv(4096).decode("utf-8", errors="ignore")
                        if not chunk:
                            break
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            self._handle_line(line.strip())
            except (ConnectionRefusedError, OSError) as e:
                if not self.reconnect:
                    logger.error("gpsd connection failed: %s", e)
                    return
                logger.warning("gpsd unavailable (%s), retrying in %ss…", e, self.reconnect_delay)
                self._stop_event.wait(self.reconnect_delay)

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return

        if msg.get("class") != "TPV":
            return

        mode = msg.get("mode", 0)
        fix_q = FixQuality.GPS if mode >= 2 else FixQuality.NO_FIX

        lat = msg.get("lat")
        lon = msg.get("lon")
        alt = msg.get("altMSL") or msg.get("alt")
        speed = msg.get("speed")
        heading = msg.get("track")

        ts_str = msg.get("time")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(timezone.utc)
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        data = GPSData(
            timestamp=ts,
            latitude=lat,
            longitude=lon,
            altitude=float(alt) if alt is not None else None,
            speed=float(speed) if speed is not None else None,
            heading=float(heading) if heading is not None else None,
            fix_quality=fix_q,
        )

        self._last_data = data
        self._dispatch(data)

    def _dispatch(self, data: GPSData) -> None:
        for cb in list(self._callbacks):
            try:
                cb(data)
            except Exception as e:
                logger.warning("Callback error: %s", e)

        if self._loop and self._loop.is_running() and self._queues:
            for q in list(self._queues):
                try:
                    self._loop.call_soon_threadsafe(q.put_nowait, data)
                except asyncio.QueueFull:
                    pass

    def __enter__(self) -> "GPSDReader":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
