"""CLI entry points for gps-mouse.

Commands:
    gps-server   Start GPS reader + ZMQ publisher (+ optional API/MQTT/logging)
    gps-read     Print GPS data to terminal
    gps-log      Log GPS data to CSV / GPX file
    gps-api      Start only the REST API + live map dashboard
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ------------------------------------------------------------------
# gps-server
# ------------------------------------------------------------------

def cmd_server(argv: list[str] | None = None) -> None:
    """Full GPS server: serial → ZMQ + optional API, MQTT, logging."""
    p = argparse.ArgumentParser(
        prog="gps-server",
        description="Read GPS and broadcast via ZMQ (+ optional API/MQTT/logging)",
    )
    p.add_argument("--port",        default="/dev/ttyACM0", help="Serial port")
    p.add_argument("--baudrate",    default=9600, type=int)
    p.add_argument("--zmq",         default="tcp://127.0.0.1:5557", help="ZMQ address")
    p.add_argument("--no-zmq",      action="store_true", help="Disable ZMQ")
    p.add_argument("--api",         action="store_true", help="Enable REST API + dashboard")
    p.add_argument("--api-port",    default=8080, type=int)
    p.add_argument("--api-host",    default="0.0.0.0")
    p.add_argument("--mqtt",        action="store_true", help="Enable MQTT")
    p.add_argument("--mqtt-broker", default="localhost")
    p.add_argument("--mqtt-port",   default=1883, type=int)
    p.add_argument("--mqtt-topic",  default="gps/data")
    p.add_argument("--csv",         metavar="FILE", help="Log to CSV file")
    p.add_argument("--gpx",         metavar="FILE", help="Log to GPX file")
    p.add_argument("--config",      metavar="FILE", help="YAML config file")
    p.add_argument("--log-level",   default="INFO")
    p.add_argument("--no-reconnect", action="store_true")
    args = p.parse_args(argv)

    _setup_logging(args.log_level)

    from .reader import GPSReader
    from .publisher import GPSPublisher

    reader = GPSReader(
        port=args.port,
        baudrate=args.baudrate,
        reconnect=not args.no_reconnect,
    )

    components = [reader]

    if not args.no_zmq:
        pub = GPSPublisher(address=args.zmq)
        pub.attach(reader)
        components.append(pub)
        print(f"ZMQ broadcasting on {args.zmq}")

    if args.mqtt:
        from .mqtt import GPSMQTTPublisher
        mqtt = GPSMQTTPublisher(
            broker=args.mqtt_broker,
            port=args.mqtt_port,
            topic=args.mqtt_topic,
        )
        mqtt.attach(reader)
        components.append(mqtt)
        print(f"MQTT → {args.mqtt_broker}:{args.mqtt_port}/{args.mqtt_topic}")

    if args.csv or args.gpx:
        from .logger import GPSLogger
        gps_logger = GPSLogger(csv_path=args.csv, gpx_path=args.gpx)
        reader.add_callback(gps_logger.record)
        components.append(gps_logger)
        if args.csv:
            print(f"CSV logging → {args.csv}")
        if args.gpx:
            print(f"GPX logging → {args.gpx}")

    reader.start()
    print(f"GPS reading from {args.port} @ {args.baudrate} baud")

    def _shutdown(*_):
        print("\nShutting down…")
        reader.stop()
        for c in components:
            if hasattr(c, "stop"):
                c.stop()
            if hasattr(c, "close"):
                c.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.api:
        from .api import GPSApi
        api = GPSApi(reader, host=args.api_host, port=args.api_port)
        print(f"Dashboard → http://{args.api_host}:{args.api_port}")
        api.serve()  # blocking
    else:
        print("Press Ctrl+C to stop")
        while True:
            d = reader.last
            if d.has_fix:
                status = (
                    f"\rlat={d.latitude:.6f}  lon={d.longitude:.6f}  "
                    f"alt={d.altitude:.1f}m  "
                    f"speed={d.speed_kmh:.1f}km/h  sats={d.num_satellites}"
                )
            else:
                status = f"\r[NO FIX] sats={d.num_satellites}          "
            print(status, end="", flush=True)
            time.sleep(1)


# ------------------------------------------------------------------
# gps-read
# ------------------------------------------------------------------

def cmd_read(argv: list[str] | None = None) -> None:
    """Print GPS data to terminal."""
    p = argparse.ArgumentParser(prog="gps-read", description="Read and print GPS data")
    p.add_argument("--port",     default="/dev/ttyACM0")
    p.add_argument("--baudrate", default=9600, type=int)
    p.add_argument("--log-level", default="WARNING")
    args = p.parse_args(argv)

    _setup_logging(args.log_level)

    from .reader import GPSReader

    def on_data(data):
        if data.has_fix:
            alt     = f"{data.altitude:.1f}m"     if data.altitude  is not None else "---"
            speed   = f"{data.speed_kmh:.1f}km/h" if data.speed_kmh is not None else "---"
            heading = f"{data.heading:.1f}°"       if data.heading   is not None else "---"
            print(f"lat={data.latitude:.6f}  lon={data.longitude:.6f}  "
                  f"alt={alt}  speed={speed}  heading={heading}  sats={data.num_satellites}")
        else:
            print(f"[NO FIX] sats={data.num_satellites}")

    with GPSReader(port=args.port, baudrate=args.baudrate) as reader:
        reader.add_callback(on_data)
        print(f"Reading from {args.port} — Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


# ------------------------------------------------------------------
# gps-log
# ------------------------------------------------------------------

def cmd_log(argv: list[str] | None = None) -> None:
    """Log GPS data to CSV and/or GPX file."""
    p = argparse.ArgumentParser(prog="gps-log", description="Log GPS data to file")
    p.add_argument("--port",     default="/dev/ttyACM0")
    p.add_argument("--baudrate", default=9600, type=int)
    p.add_argument("--csv",      metavar="FILE", default="gps_log.csv")
    p.add_argument("--gpx",      metavar="FILE", default=None)
    p.add_argument("--log-level", default="WARNING")
    args = p.parse_args(argv)

    _setup_logging(args.log_level)

    from .reader import GPSReader
    from .logger import GPSLogger

    with GPSLogger(csv_path=args.csv, gpx_path=args.gpx) as gps_logger:
        with GPSReader(port=args.port, baudrate=args.baudrate) as reader:
            reader.add_callback(gps_logger.record)
            print(f"Logging to {args.csv}" + (f" + {args.gpx}" if args.gpx else ""))
            print("Ctrl+C to stop")
            try:
                while True:
                    time.sleep(1)
                    print(f"\r{gps_logger.record_count} fixes recorded", end="", flush=True)
            except KeyboardInterrupt:
                print(f"\nDone — {gps_logger.record_count} fixes recorded.")


# ------------------------------------------------------------------
# gps-api
# ------------------------------------------------------------------

def cmd_api(argv: list[str] | None = None) -> None:
    """Start REST API + live map dashboard."""
    p = argparse.ArgumentParser(prog="gps-api", description="GPS REST API + live map")
    p.add_argument("--port",      default="/dev/ttyACM0")
    p.add_argument("--baudrate",  default=9600, type=int)
    p.add_argument("--host",      default="0.0.0.0")
    p.add_argument("--api-port",  default=8080, type=int)
    p.add_argument("--log-level", default="WARNING")
    args = p.parse_args(argv)

    _setup_logging(args.log_level)

    from .reader import GPSReader
    from .api import GPSApi

    reader = GPSReader(port=args.port, baudrate=args.baudrate)
    reader.start()

    api = GPSApi(reader, host=args.host, port=args.api_port)
    print(f"Dashboard → http://{args.host}:{args.api_port}")
    try:
        api.serve()
    finally:
        reader.stop()
