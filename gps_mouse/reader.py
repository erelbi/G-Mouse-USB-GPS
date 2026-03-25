"""GPS serial reader - parses NMEA sentences and dispatches to subscribers."""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import AsyncIterator, Callable

import pynmea2
import serial

from .exceptions import GPSDeviceNotFound, GPSPermissionError, GPSParseError
from .models import FixQuality, GPSData

logger = logging.getLogger(__name__)

_SUPPORTED = {"GGA", "RMC", "VTG"}

GPSCallback = Callable[[GPSData], None]


class GPSReader:
    """Reads data from the GPS device and dispatches to subscribers.

    Synchronous usage:
        reader = GPSReader()
        reader.add_callback(lambda d: print(d))
        reader.start()
        ...
        reader.stop()

    Asynchronous usage:
        async for data in GPSReader().stream():
            print(data)
    """

    DEFAULT_PORT = "/dev/ttyACM0"
    DEFAULT_BAUDRATE = 9600

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 2.0,
        reconnect: bool = True,
        reconnect_delay: float = 5.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay

        self._callbacks: list[GPSCallback] = []
        self._queues: list[asyncio.Queue[GPSData]] = []
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_data = GPSData(timestamp=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Subscription API
    # ------------------------------------------------------------------

    def add_callback(self, cb: GPSCallback) -> None:
        """Register a callback to be called on every new GPS reading."""
        self._callbacks.append(cb)

    def remove_callback(self, cb: GPSCallback) -> None:
        self._callbacks.remove(cb)

    def _make_queue(self, maxsize: int = 100) -> asyncio.Queue[GPSData]:
        q: asyncio.Queue[GPSData] = asyncio.Queue(maxsize=maxsize)
        self._queues.append(q)
        return q

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background reading thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="gps-reader")
        self._thread.start()
        logger.info("GPSReader started: %s @ %d baud", self.port, self.baudrate)

    def stop(self) -> None:
        """Stop reading."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info("GPSReader stopped.")

    # ------------------------------------------------------------------
    # Async stream interface
    # ------------------------------------------------------------------

    async def stream(self, maxsize: int = 100) -> AsyncIterator[GPSData]:
        """Async generator: use as `async for data in reader.stream()`."""
        self._loop = asyncio.get_running_loop()
        q = self._make_queue(maxsize)
        self.start()
        try:
            while True:
                data = await q.get()
                yield data
        finally:
            self._queues.remove(q)

    # ------------------------------------------------------------------
    # Internal read loop
    # ------------------------------------------------------------------

    def _open_serial(self) -> serial.Serial:
        try:
            return serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except serial.SerialException as e:
            msg = str(e).lower()
            if "permission" in msg or "access" in msg:
                raise GPSPermissionError(
                    f"No permission to access {self.port}. "
                    "Fix: sudo usermod -aG dialout $USER && (re-login)"
                ) from e
            raise GPSDeviceNotFound(f"Could not open port: {self.port} — {e}") from e

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._serial = self._open_serial()
                logger.info("Connected to %s", self.port)
            except GPSPermissionError:
                raise  # permission errors are not recoverable
            except Exception as e:
                if not self.reconnect:
                    logger.error("Failed to open serial port: %s", e)
                    return
                logger.warning("Port unavailable (%s), retrying in %ss…", e, self.reconnect_delay)
                self._stop_event.wait(self.reconnect_delay)
                continue

            partial: dict = {}
            self._read_loop(partial)

            if self._serial and self._serial.is_open:
                self._serial.close()

            if not self.reconnect or self._stop_event.is_set():
                break
            logger.warning("Disconnected from %s, reconnecting in %ss…", self.port, self.reconnect_delay)
            self._stop_event.wait(self.reconnect_delay)

    def _read_loop(self, partial: dict) -> None:
        while not self._stop_event.is_set():
            try:
                raw = self._serial.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="ignore").strip()
                if not line.startswith("$"):
                    continue

                data = self._parse_line(line, partial)
                if data is not None:
                    self._last_data = data
                    self._dispatch(data)

            except serial.SerialException as e:
                logger.error("Serial read error: %s", e)
                return  # trigger reconnect
            except Exception as e:
                logger.debug("Line processing error: %s", e)

    def _parse_line(self, line: str, partial: dict) -> GPSData | None:
        """Parse an NMEA line; returns GPSData when a full reading is ready."""
        try:
            msg = pynmea2.parse(line)
        except pynmea2.ParseError:
            return None

        sentence_type = msg.sentence_type

        if sentence_type == "GGA":
            partial["gga"] = msg
        elif sentence_type == "RMC":
            partial["rmc"] = msg
        elif sentence_type == "VTG":
            partial["vtg"] = msg
        else:
            return None

        if "gga" not in partial:
            return None

        return self._build_data(partial)

    def _build_data(self, partial: dict) -> GPSData:
        gga = partial.get("gga")
        rmc = partial.get("rmc")
        vtg = partial.get("vtg")

        now = datetime.now(timezone.utc)

        # Timestamp
        ts = now
        if gga and gga.timestamp:
            try:
                ts = datetime.combine(now.date(), gga.timestamp, tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                pass

        # Position — pynmea2's .latitude/.longitude already apply N/S/E/W sign
        lat = lon = None
        try:
            if gga and gga.lat:
                lat = gga.latitude
            if gga and gga.lon:
                lon = gga.longitude
        except (ValueError, AttributeError):
            pass

        # Altitude
        alt = None
        try:
            if gga and gga.altitude:
                alt = float(gga.altitude)
        except (ValueError, AttributeError):
            pass

        # Speed (VTG km/h → m/s, fallback to RMC knots → m/s)
        speed = None
        try:
            if vtg and vtg.spd_over_grnd_kmph:
                speed = float(vtg.spd_over_grnd_kmph) / 3.6
            elif rmc and rmc.spd_over_grnd:
                speed = float(rmc.spd_over_grnd) * 0.514444  # knots → m/s
            # Noise filter: treat speeds below 1.5 km/h as stationary
            if speed is not None and speed < (1.5 / 3.6):
                speed = 0.0
        except (ValueError, AttributeError):
            pass

        # Heading
        heading = None
        try:
            if vtg and vtg.true_track:
                heading = float(vtg.true_track)
            elif rmc and rmc.true_course:
                heading = float(rmc.true_course)
        except (ValueError, AttributeError):
            pass

        # Fix quality
        fix_q = FixQuality.NO_FIX
        try:
            if gga and gga.gps_qual is not None:
                fix_q = FixQuality(int(gga.gps_qual))
        except (ValueError, AttributeError):
            pass

        # Satellite count
        num_sats = 0
        try:
            if gga and gga.num_sats:
                num_sats = int(gga.num_sats)
        except (ValueError, AttributeError):
            pass

        # HDOP
        hdop = None
        try:
            if gga and gga.horizontal_dil:
                hdop = float(gga.horizontal_dil)
        except (ValueError, AttributeError):
            pass

        return GPSData(
            timestamp=ts,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            speed=speed,
            heading=heading,
            fix_quality=fix_q,
            num_satellites=num_sats,
            hdop=hdop,
            raw_sentence=gga.render() if gga else "",
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, data: GPSData) -> None:
        # Synchronous callbacks
        for cb in list(self._callbacks):
            try:
                cb(data)
            except Exception as e:
                logger.warning("Callback error: %s", e)

        # Async queues
        if self._loop and self._loop.is_running() and self._queues:
            for q in list(self._queues):
                try:
                    self._loop.call_soon_threadsafe(q.put_nowait, data)
                except asyncio.QueueFull:
                    logger.debug("Queue full, data dropped.")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def last(self) -> GPSData:
        """Most recently received GPS data."""
        return self._last_data

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def __enter__(self) -> "GPSReader":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
