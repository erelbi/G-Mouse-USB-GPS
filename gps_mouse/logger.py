"""GPS data logger — writes CSV tracks and GPX files.

Usage:
    from gps_mouse import GPSReader
    from gps_mouse.logger import GPSLogger

    logger = GPSLogger(csv_path="track.csv", gpx_path="track.gpx")
    reader = GPSReader()
    reader.add_callback(logger.record)
    reader.start()
"""
from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import GPSData


class GPSLogger:
    """Records GPS fixes to CSV and/or GPX files.

    Args:
        csv_path: Path to CSV file. Pass None to disable.
        gpx_path: Path to GPX file. Pass None to disable.
        only_fixes: Skip records without a valid fix (default True).
    """

    def __init__(
        self,
        csv_path: str | None = None,
        gpx_path: str | None = None,
        only_fixes: bool = True,
    ) -> None:
        self.csv_path = csv_path
        self.gpx_path = gpx_path
        self.only_fixes = only_fixes
        self._lock = threading.Lock()
        self._count = 0

        if csv_path:
            self._init_csv(csv_path)
        if gpx_path:
            self._init_gpx(gpx_path)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def record(self, data: "GPSData") -> None:
        """Callback — pass to GPSReader.add_callback()."""
        if self.only_fixes and not data.has_fix:
            return
        with self._lock:
            if self.csv_path:
                self._write_csv(data)
            if self.gpx_path:
                self._write_gpx_point(data)
            self._count += 1

    def close(self) -> None:
        """Finalize GPX file (writes closing tags)."""
        if self.gpx_path and os.path.exists(self.gpx_path):
            self._close_gpx()

    @property
    def record_count(self) -> int:
        return self._count

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def _init_csv(self, path: str) -> None:
        write_header = not Path(path).exists()
        self._csv_file = open(path, "a", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        if write_header:
            self._csv_writer.writerow([
                "timestamp", "latitude", "longitude", "altitude_m",
                "speed_kmh", "heading_deg", "fix_quality",
                "num_satellites", "hdop",
            ])
            self._csv_file.flush()

    def _write_csv(self, data: "GPSData") -> None:
        self._csv_writer.writerow([
            data.timestamp.isoformat(),
            data.latitude,
            data.longitude,
            data.altitude,
            round(data.speed_kmh, 2) if data.speed_kmh is not None else None,
            data.heading,
            int(data.fix_quality),
            data.num_satellites,
            data.hdop,
        ])
        self._csv_file.flush()

    # ------------------------------------------------------------------
    # GPX
    # ------------------------------------------------------------------

    def _init_gpx(self, path: str) -> None:
        self._gpx_file = open(path, "w")
        self._gpx_file.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="gps-mouse" '
            'xmlns="http://www.topografix.com/GPX/1/1">\n'
            '  <trk><name>GPS Track</name><trkseg>\n'
        )
        self._gpx_file.flush()

    def _write_gpx_point(self, data: "GPSData") -> None:
        lat = data.latitude or 0.0
        lon = data.longitude or 0.0
        ts = data.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        ele = f"    <ele>{data.altitude:.1f}</ele>\n" if data.altitude is not None else ""
        spd = f"    <speed>{data.speed:.2f}</speed>\n" if data.speed is not None else ""

        self._gpx_file.write(
            f'  <trkpt lat="{lat:.8f}" lon="{lon:.8f}">\n'
            f"    <time>{ts}</time>\n"
            f"{ele}{spd}"
            f"  </trkpt>\n"
        )
        self._gpx_file.flush()

    def _close_gpx(self) -> None:
        self._gpx_file.write("  </trkseg></trk>\n</gpx>\n")
        self._gpx_file.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "GPSLogger":
        return self

    def __exit__(self, *_) -> None:
        self.close()
