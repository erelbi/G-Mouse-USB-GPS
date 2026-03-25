"""Tests for gps_mouse.models."""
import json
from datetime import datetime, timezone

import pytest

from gps_mouse.models import FixQuality, GPSData


TS = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def make_fix(**kwargs) -> GPSData:
    defaults = dict(
        timestamp=TS,
        latitude=39.972672,
        longitude=32.641504,
        altitude=858.5,
        speed=2.0,
        heading=90.0,
        fix_quality=FixQuality.GPS,
        num_satellites=7,
        hdop=1.2,
    )
    defaults.update(kwargs)
    return GPSData(**defaults)


# ------------------------------------------------------------------
# FixQuality
# ------------------------------------------------------------------

class TestFixQuality:
    def test_values(self):
        assert FixQuality.NO_FIX == 0
        assert FixQuality.GPS == 1
        assert FixQuality.DGPS == 2
        assert FixQuality.RTK == 4

    def test_ordering(self):
        assert FixQuality.NO_FIX < FixQuality.GPS
        assert FixQuality.GPS < FixQuality.RTK


# ------------------------------------------------------------------
# GPSData.has_fix
# ------------------------------------------------------------------

class TestHasFix:
    def test_has_fix_when_quality_and_lat_present(self):
        data = make_fix()
        assert data.has_fix is True

    def test_no_fix_when_quality_zero(self):
        data = make_fix(fix_quality=FixQuality.NO_FIX)
        assert data.has_fix is False

    def test_no_fix_when_latitude_none(self):
        data = make_fix(latitude=None)
        assert data.has_fix is False

    def test_no_fix_when_both_missing(self):
        data = GPSData(timestamp=TS)
        assert data.has_fix is False


# ------------------------------------------------------------------
# GPSData.speed_kmh
# ------------------------------------------------------------------

class TestSpeedKmh:
    def test_conversion(self):
        data = make_fix(speed=10.0)  # 10 m/s
        assert abs(data.speed_kmh - 36.0) < 0.001

    def test_zero(self):
        data = make_fix(speed=0.0)
        assert data.speed_kmh == 0.0

    def test_none(self):
        data = make_fix(speed=None)
        assert data.speed_kmh is None


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_has_all_fields(self):
        data = make_fix()
        d = data.to_dict()
        for field in ("latitude", "longitude", "altitude", "speed",
                      "heading", "fix_quality", "num_satellites", "hdop", "timestamp"):
            assert field in d

    def test_to_dict_timestamp_is_iso_string(self):
        data = make_fix()
        d = data.to_dict()
        assert isinstance(d["timestamp"], str)
        datetime.fromisoformat(d["timestamp"])  # must not raise

    def test_to_dict_fix_quality_is_int(self):
        data = make_fix()
        d = data.to_dict()
        assert isinstance(d["fix_quality"], int)
        assert d["fix_quality"] == 1

    def test_to_json_is_valid_json(self):
        data = make_fix()
        parsed = json.loads(data.to_json())
        assert parsed["latitude"] == pytest.approx(39.972672)

    def test_roundtrip_dict(self):
        original = make_fix()
        restored = GPSData.from_dict(original.to_dict())
        assert restored.latitude == pytest.approx(original.latitude)
        assert restored.longitude == pytest.approx(original.longitude)
        assert restored.fix_quality == original.fix_quality
        assert restored.timestamp == original.timestamp

    def test_roundtrip_json(self):
        original = make_fix()
        restored = GPSData.from_json(original.to_json())
        assert restored.altitude == pytest.approx(original.altitude)
        assert restored.num_satellites == original.num_satellites

    def test_from_dict_fix_quality_converted(self):
        data = make_fix()
        d = data.to_dict()
        restored = GPSData.from_dict(d)
        assert isinstance(restored.fix_quality, FixQuality)

    def test_roundtrip_no_fix(self):
        original = GPSData(timestamp=TS)
        restored = GPSData.from_json(original.to_json())
        assert restored.has_fix is False
        assert restored.latitude is None


# ------------------------------------------------------------------
# __repr__
# ------------------------------------------------------------------

class TestRepr:
    def test_repr_with_fix(self):
        data = make_fix()
        r = repr(data)
        assert "lat=" in r
        assert "lon=" in r
        assert "sats=7" in r

    def test_repr_no_fix(self):
        data = GPSData(timestamp=TS)
        assert "NO FIX" in repr(data)


# ------------------------------------------------------------------
# Southern / Western hemisphere
# ------------------------------------------------------------------

class TestHemisphere:
    def test_southern_latitude_negative(self):
        data = make_fix(latitude=-33.8688)
        assert data.latitude < 0

    def test_western_longitude_negative(self):
        data = make_fix(longitude=-73.5673)
        assert data.longitude < 0

    def test_roundtrip_south_west(self):
        original = make_fix(latitude=-33.8688, longitude=-73.5673)
        restored = GPSData.from_json(original.to_json())
        assert restored.latitude == pytest.approx(-33.8688)
        assert restored.longitude == pytest.approx(-73.5673)
