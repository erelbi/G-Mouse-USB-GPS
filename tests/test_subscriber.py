"""Tests for gps_mouse.subscriber."""
import json
from datetime import datetime, timezone

import pytest

from gps_mouse.models import FixQuality, GPSData
from gps_mouse.subscriber import GPSSubscriber


TS = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def make_fix_json() -> str:
    data = GPSData(
        timestamp=TS,
        latitude=39.972672,
        longitude=32.641504,
        altitude=858.5,
        speed=0.0,
        fix_quality=FixQuality.GPS,
        num_satellites=7,
        hdop=1.2,
    )
    return data.to_json()


def make_zmq_message(topic: str, data_json: str) -> str:
    return f"{topic} {data_json}"


# ------------------------------------------------------------------
# _parse_message
# ------------------------------------------------------------------

class TestParseMessage:
    def test_valid_fix_message(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert data is not None
        assert data.has_fix
        assert data.latitude == pytest.approx(39.972672)

    def test_valid_nofix_message(self):
        nofix = GPSData(timestamp=TS).to_json()
        msg = make_zmq_message("gps.nofix", nofix)
        data = GPSSubscriber._parse_message(msg)
        assert data is not None
        assert data.has_fix is False

    def test_malformed_message_returns_none(self):
        data = GPSSubscriber._parse_message("no-space-here")
        assert data is None

    def test_invalid_json_returns_none(self):
        data = GPSSubscriber._parse_message("gps.fix {not valid json}")
        assert data is None

    def test_empty_string_returns_none(self):
        data = GPSSubscriber._parse_message("")
        assert data is None

    def test_latitude_preserved(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert data.latitude == pytest.approx(39.972672)

    def test_longitude_preserved(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert data.longitude == pytest.approx(32.641504)

    def test_altitude_preserved(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert data.altitude == pytest.approx(858.5)

    def test_num_satellites_preserved(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert data.num_satellites == 7

    def test_fix_quality_is_enum(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert isinstance(data.fix_quality, FixQuality)

    def test_timestamp_is_datetime(self):
        msg = make_zmq_message("gps.fix", make_fix_json())
        data = GPSSubscriber._parse_message(msg)
        assert isinstance(data.timestamp, datetime)

    def test_json_with_extra_spaces_in_topic(self):
        # topic and json separated by single space — standard
        msg = "gps.fix " + make_fix_json()
        data = GPSSubscriber._parse_message(msg)
        assert data is not None


# ------------------------------------------------------------------
# Constructor defaults
# ------------------------------------------------------------------

class TestConstructor:
    def test_default_address(self):
        from gps_mouse.publisher import DEFAULT_ADDRESS
        sub = GPSSubscriber()
        assert sub.address == DEFAULT_ADDRESS

    def test_default_topic(self):
        sub = GPSSubscriber()
        assert sub.topic == "gps"

    def test_custom_address(self):
        sub = GPSSubscriber(address="tcp://192.168.1.10:5557")
        assert sub.address == "tcp://192.168.1.10:5557"

    def test_custom_topic(self):
        sub = GPSSubscriber(topic="gps.fix")
        assert sub.topic == "gps.fix"
