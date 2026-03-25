"""Example 4: GPS stream with asyncio.

Usage:
    python examples/04_async_stream.py
"""
import asyncio
from gps_mouse import GPSReader, GPSPublisher, GPSSubscriber


async def producer():
    """Read GPS and broadcast over ZMQ."""
    reader = GPSReader()
    pub = GPSPublisher()
    pub.attach(reader)
    reader.start()
    print("Producer started.")
    await asyncio.sleep(60)  # broadcast for 60 seconds
    reader.stop()
    pub.stop()


async def consumer():
    """Receive GPS data asynchronously from ZMQ."""
    await asyncio.sleep(1)  # wait for producer to start
    sub = GPSSubscriber()
    async for data in sub.stream():
        print(f"[CONSUMER] {data}")


async def main():
    await asyncio.gather(producer(), consumer())


if __name__ == "__main__":
    asyncio.run(main())
