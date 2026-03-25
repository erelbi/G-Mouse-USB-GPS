"""Tests for gps_mouse.reader — NMEA parsing and noise filter."""
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import serial

from gps_mouse.exceptions import GPSDeviceNotFound, GPSPermissionError
from gps_mouse.models import FixQuality, GPSData
from gps_mouse.reader import GPSReader


# ------------------------------------------------------------------
# Valid NMEA sentences (checksums verified)
# ------------------------------------------------------------------

GGA_FIX     = "$GPGGA,120000.00,3958.3603,N,03238.4902,E,1,07,1.20,858.5,M,32.1,M,,*5F"
GGA_NO_FIX  = "$GPGGA,120000.00,,,,,,0,00,99.99,,M,,M,,*49"
RMC_MOVING  = "$GPRMC,120000.00,A,3958.3603,N,03238.4902,E,5.00,90.0,250326,,,A*55"
VTG_MOVING  = "$GPVTG,90.0,T,,M,9.26,N,17.16,K,A*08"
VTG_STILL   = "$GPVTG,,,,,0.00,N,0.00,K,N*35"


def make_reader(**kwargs) -> GPSReader:
    defaults = {"port": "/dev/ttyACM0"}
    defaults.update(kwargs)
    return GPSReader(**defaults)


# ------------------------------------------------------------------
# _parse_line
# ------------------------------------------------------------------

class TestParseLine:
    def test_gga_stored_in_partial(self):
        reader = make_reader()
        partial = {}
        result = reader._parse_line(GGA_FIX, partial)
        assert "gga" in partial
        assert result is not None

    def test_rmc_stored_but_no_output_without_gga(self):
        reader = make_reader()
        partial = {}
        result = reader._parse_line(RMC_MOVING, partial)
        assert "rmc" in partial
        assert result is None  # no GGA yet

    def test_vtg_stored_but_no_output_without_gga(self):
        reader = make_reader()
        partial = {}
        result = reader._parse_line(VTG_MOVING, partial)
        assert "vtg" in partial
        assert result is None

    def test_gga_after_rmc_produces_data(self):
        reader = make_reader()
        partial = {}
        reader._parse_line(RMC_MOVING, partial)
        result = reader._parse_line(GGA_FIX, partial)
        assert result is not None
        assert isinstance(result, GPSData)

    def test_invalid_sentence_returns_none(self):
        reader = make_reader()
        result = reader._parse_line("$GPXXX,garbage,,*00", {})
        assert result is None

    def test_non_nmea_line_returns_none(self):
        reader = make_reader()
        result = reader._parse_line("not nmea at all", {})
        assert result is None

    def test_unknown_sentence_type_returns_none(self):
        reader = make_reader()
        partial = {}
        result = reader._parse_line("$GPGSV,3,1,12*73", partial)
        assert result is None


# ------------------------------------------------------------------
# _build_data — position
# ------------------------------------------------------------------

class TestBuildDataPosition:
    def _build(self, gga_str, rmc_str=None, vtg_str=None) -> GPSData:
        reader = make_reader()
        partial = {}
        reader._parse_line(gga_str, partial)
        if rmc_str:
            reader._parse_line(rmc_str, partial)
        if vtg_str:
            reader._parse_line(vtg_str, partial)
        return reader._build_data(partial)

    def test_latitude_north(self):
        data = self._build(GGA_FIX)
        assert data.latitude == pytest.approx(39.972672, abs=1e-4)

    def test_longitude_east(self):
        data = self._build(GGA_FIX)
        assert data.longitude == pytest.approx(32.641503, abs=1e-4)

    def test_altitude(self):
        data = self._build(GGA_FIX)
        assert data.altitude == pytest.approx(858.5, abs=0.1)

    def test_fix_quality_gps(self):
        data = self._build(GGA_FIX)
        assert data.fix_quality == FixQuality.GPS

    def test_num_satellites(self):
        data = self._build(GGA_FIX)
        assert data.num_satellites == 7

    def test_hdop(self):
        data = self._build(GGA_FIX)
        assert data.hdop == pytest.approx(1.2, abs=0.01)

    def test_no_fix_quality(self):
        data = self._build(GGA_NO_FIX)
        assert data.fix_quality == FixQuality.NO_FIX

    def test_no_fix_latitude_none(self):
        data = self._build(GGA_NO_FIX)
        assert data.latitude is None

    def test_southern_hemisphere(self):
        # Recompute checksum after replacing N → S
        body = "GPGGA,120000.00,3958.3603,S,03238.4902,E,1,07,1.20,858.5,M,32.1,M,,"
        cs = 0
        for c in body:
            cs ^= ord(c)
        gga_south = f"${body}*{cs:02X}"
        data = self._build(gga_south)
        assert data.latitude < 0

    def test_western_hemisphere(self):
        body = "GPGGA,120000.00,3958.3603,N,03238.4902,W,1,07,1.20,858.5,M,32.1,M,,"
        cs = 0
        for c in body:
            cs ^= ord(c)
        gga_west = f"${body}*{cs:02X}"
        data = self._build(gga_west)
        assert data.longitude < 0


# ------------------------------------------------------------------
# _build_data — speed noise filter
# ------------------------------------------------------------------

class TestSpeedNoise:
    def _build_with_vtg_kmh(self, kmh: float) -> GPSData:
        reader = make_reader()
        partial = {}
        reader._parse_line(GGA_FIX, partial)
        vtg_mock = MagicMock()
        vtg_mock.sentence_type = "VTG"
        vtg_mock.spd_over_grnd_kmph = str(kmh)
        vtg_mock.true_track = "90.0"
        partial["vtg"] = vtg_mock
        return reader._build_data(partial)

    def test_speed_above_threshold_passes(self):
        data = self._build_with_vtg_kmh(5.0)
        assert data.speed is not None
        assert data.speed > 0

    def test_speed_below_threshold_zeroed(self):
        data = self._build_with_vtg_kmh(1.0)
        assert data.speed == 0.0

    def test_speed_at_noise_floor_zeroed(self):
        data = self._build_with_vtg_kmh(1.4)
        assert data.speed == 0.0

    def test_speed_kmh_converts_correctly(self):
        data = self._build_with_vtg_kmh(36.0)
        assert data.speed == pytest.approx(10.0, abs=0.01)
        assert data.speed_kmh == pytest.approx(36.0, abs=0.1)


# ------------------------------------------------------------------
# _open_serial — permission / not-found errors
# ------------------------------------------------------------------

class TestOpenSerial:
    def test_permission_error_raises_gps_permission_error(self):
        reader = make_reader()
        with patch("serial.Serial", side_effect=serial.SerialException("permission denied")):
            with pytest.raises(GPSPermissionError):
                reader._open_serial()

    def test_not_found_raises_gps_device_not_found(self):
        reader = make_reader(port="/dev/nonexistent")
        with patch("serial.Serial", side_effect=serial.SerialException("no such file")):
            with pytest.raises(GPSDeviceNotFound):
                reader._open_serial()


# ------------------------------------------------------------------
# Callback dispatch
# ------------------------------------------------------------------

class TestCallbacks:
    def test_callback_called_on_data(self):
        received = []
        reader = make_reader()
        reader.add_callback(received.append)

        partial = {}
        reader._parse_line(GGA_FIX, partial)
        data = reader._build_data(partial)
        reader._dispatch(data)

        assert len(received) == 1
        assert received[0].has_fix

    def test_multiple_callbacks(self):
        results = [[], []]
        reader = make_reader()
        reader.add_callback(results[0].append)
        reader.add_callback(results[1].append)

        partial = {}
        reader._parse_line(GGA_FIX, partial)
        data = reader._build_data(partial)
        reader._dispatch(data)

        assert len(results[0]) == 1
        assert len(results[1]) == 1

    def test_failing_callback_does_not_stop_others(self):
        received = []
        reader = make_reader()
        reader.add_callback(lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
        reader.add_callback(received.append)

        partial = {}
        reader._parse_line(GGA_FIX, partial)
        data = reader._build_data(partial)
        reader._dispatch(data)

        assert len(received) == 1

    def test_remove_callback(self):
        received = []
        reader = make_reader()
        cb = received.append
        reader.add_callback(cb)
        reader.remove_callback(cb)

        partial = {}
        reader._parse_line(GGA_FIX, partial)
        data = reader._build_data(partial)
        reader._dispatch(data)

        assert received == []


# ------------------------------------------------------------------
# Start / Stop / is_running
# ------------------------------------------------------------------

class TestStartStop:
    def test_not_running_initially(self):
        reader = make_reader()
        assert reader.is_running is False

    def test_start_fails_gracefully_when_port_missing(self):
        reader = make_reader(port="/dev/nonexistent999")
        reader.start()
        time.sleep(0.3)
        reader.stop()

    def test_context_manager_stops_reader(self):
        reader = make_reader(port="/dev/nonexistent999")
        with reader:
            pass
        assert reader.is_running is False

    def test_double_start_is_safe(self):
        reader = make_reader(port="/dev/nonexistent999")
        reader.start()
        reader.start()  # second call should be a no-op
        reader.stop()

    def test_last_returns_gpsdata(self):
        reader = make_reader()
        assert isinstance(reader.last, GPSData)
