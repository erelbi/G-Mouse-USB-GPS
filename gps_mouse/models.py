"""GPS data models."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import IntEnum


class FixQuality(IntEnum):
    NO_FIX = 0
    GPS = 1
    DGPS = 2
    PPS = 3
    RTK = 4
    FLOAT_RTK = 5
    ESTIMATED = 6
    MANUAL = 7
    SIMULATION = 8


@dataclass
class GPSData:
    """Represents a single GPS measurement."""

    timestamp: datetime
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None        # metres (MSL)
    speed: float | None = None           # m/s
    heading: float | None = None         # degrees (True North)
    fix_quality: FixQuality = FixQuality.NO_FIX
    num_satellites: int = 0
    hdop: float | None = None            # Horizontal dilution of precision
    raw_sentence: str = ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def has_fix(self) -> bool:
        return self.fix_quality > FixQuality.NO_FIX and self.latitude is not None

    @property
    def speed_kmh(self) -> float | None:
        return self.speed * 3.6 if self.speed is not None else None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["fix_quality"] = int(self.fix_quality)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "GPSData":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        d["fix_quality"] = FixQuality(d["fix_quality"])
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "GPSData":
        return cls.from_dict(json.loads(s))

    def __repr__(self) -> str:
        if self.has_fix:
            return (
                f"GPSData(lat={self.latitude:.6f}, lon={self.longitude:.6f}, "
                f"alt={self.altitude}m, speed={self.speed_kmh:.1f}km/h, "
                f"sats={self.num_satellites})"
            )
        return f"GPSData(NO FIX, sats={self.num_satellites})"
