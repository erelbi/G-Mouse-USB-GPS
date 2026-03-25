"""Tests for gps_mouse.publisher."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import zmq

from gps_mouse.exceptions import GPSPublisherError
from gps_mouse.models import FixQuality, GPSData
from gps_mouse.publisher import GPSPublisher, DEFAULT_ADDRESS


TS = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def make_data(has_fix=True) -> GPSData:
    if has_fix:
        return GPSData(
            timestamp=TS,
            latitude=39.972672,
            longitude=32.641504,
            altitude=858.5,
            fix_quality=FixQuality.GPS,
            num_satellites=7,
        )
    return GPSData(timestamp=TS)


# ------------------------------------------------------------------
# Default address
# ------------------------------------------------------------------

def test_default_address():
    pub = GPSPublisher()
    assert pub.address == DEFAULT_ADDRESS


def test_custom_address():
    pub = GPSPublisher(address="tcp://127.0.0.1:9999")
    assert pub.address == "tcp://127.0.0.1:9999"


# ------------------------------------------------------------------
# start / stop
# ------------------------------------------------------------------

class TestLifecycle:
    def test_start_binds_socket(self):
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19001")
            pub.start()
            mock_sock.bind.assert_called_once_with("tcp://127.0.0.1:19001")

    def test_double_start_binds_only_once(self):
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19002")
            pub.start()
            pub.start()
            assert mock_sock.bind.call_count == 1

    def test_stop_closes_socket(self):
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19003")
            pub.start()
            pub.stop()
            mock_sock.close.assert_called_once()

    def test_start_zmq_error_raises_publisher_error(self):
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = zmq.ZMQError("address in use")
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19004")
            with pytest.raises(GPSPublisherError):
                pub.start()

    def test_context_manager(self):
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            with GPSPublisher(address="tcp://127.0.0.1:19005") as pub:
                pass
            mock_sock.close.assert_called_once()


# ------------------------------------------------------------------
# publish — topic selection
# ------------------------------------------------------------------

class TestPublish:
    def _make_pub_with_mock(self, address="tcp://127.0.0.1:19010"):
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock
        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address=address)
            pub.start()
            return pub, mock_sock

    def test_fix_uses_gps_fix_topic(self):
        pub, sock = self._make_pub_with_mock("tcp://127.0.0.1:19011")
        pub.publish(make_data(has_fix=True))
        call_args = sock.send_string.call_args[0][0]
        assert call_args.startswith("gps.fix ")

    def test_no_fix_uses_gps_nofix_topic(self):
        pub, sock = self._make_pub_with_mock("tcp://127.0.0.1:19012")
        pub.publish(make_data(has_fix=False))
        call_args = sock.send_string.call_args[0][0]
        assert call_args.startswith("gps.nofix ")

    def test_payload_is_valid_json(self):
        import json
        pub, sock = self._make_pub_with_mock("tcp://127.0.0.1:19013")
        pub.publish(make_data(has_fix=True))
        raw = sock.send_string.call_args[0][0]
        _, json_part = raw.split(" ", 1)
        parsed = json.loads(json_part)
        assert "latitude" in parsed
        assert parsed["latitude"] == pytest.approx(39.972672)

    def test_zmq_again_is_silently_ignored(self):
        pub, sock = self._make_pub_with_mock("tcp://127.0.0.1:19014")
        sock.send_string.side_effect = zmq.Again()
        pub.publish(make_data())  # must not raise

    def test_attach_registers_callback(self):
        from gps_mouse.reader import GPSReader
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19015")
            reader = GPSReader(port="/dev/nonexistent")
            pub.attach(reader)
            assert pub.publish in reader._callbacks

    def test_detach_removes_callback(self):
        from gps_mouse.reader import GPSReader
        mock_sock = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.socket.return_value = mock_sock

        with patch("zmq.Context.instance", return_value=mock_ctx):
            pub = GPSPublisher(address="tcp://127.0.0.1:19016")
            reader = GPSReader(port="/dev/nonexistent")
            pub.attach(reader)
            pub.detach(reader)
            assert pub.publish not in reader._callbacks
