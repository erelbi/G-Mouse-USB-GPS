"""GPS library exceptions."""


class GPSError(Exception):
    """Base GPS error."""


class GPSDeviceNotFound(GPSError):
    """Serial port not found or could not be opened."""


class GPSPermissionError(GPSError):
    """No permission to access the serial port.

    Fix: sudo usermod -aG dialout $USER
    """


class GPSParseError(GPSError):
    """Failed to parse NMEA sentence."""


class GPSNotRunning(GPSError):
    """Reader has not been started yet."""


class GPSPublisherError(GPSError):
    """ZMQ publish error."""


class GPSSubscriberError(GPSError):
    """ZMQ subscribe error."""
