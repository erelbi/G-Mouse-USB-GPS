"""gps_mouse — U-Blox GPS library.

Quick start:

    # Start GPS reader + ZMQ publisher (main project)
    from gps_mouse import GPSReader, GPSPublisher

    reader = GPSReader()
    pub = GPSPublisher()
    pub.attach(reader)
    reader.start()

    # Subscribe from another project
    from gps_mouse import GPSSubscriber

    for data in GPSSubscriber().iter_fixes():
        print(data.latitude, data.longitude)
"""

from .exceptions import (
    GPSDeviceNotFound,
    GPSError,
    GPSNotRunning,
    GPSParseError,
    GPSPermissionError,
    GPSPublisherError,
    GPSSubscriberError,
)
from .models import FixQuality, GPSData
from .publisher import DEFAULT_ADDRESS, GPSPublisher
from .reader import GPSReader
from .subscriber import GPSSubscriber

__all__ = [
    # Main classes
    "GPSReader",
    "GPSPublisher",
    "GPSSubscriber",
    # Data model
    "GPSData",
    "FixQuality",
    # Constants
    "DEFAULT_ADDRESS",
    # Exceptions
    "GPSError",
    "GPSDeviceNotFound",
    "GPSPermissionError",
    "GPSParseError",
    "GPSNotRunning",
    "GPSPublisherError",
    "GPSSubscriberError",
]

__version__ = "0.1.3"
