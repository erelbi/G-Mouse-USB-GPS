FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/erelbi/G-Mouse-USB-GPS"
LABEL org.opencontainers.image.description="GPS Mouse — USB GPS reader and broadcaster"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md LICENSE ./
COPY gps_mouse/ ./gps_mouse/

RUN pip install --no-cache-dir ".[all]"

# GPS device is passed via --device flag at runtime
# Serial port access requires dialout group
ENV GPS_PORT=/dev/ttyACM0
ENV GPS_BAUDRATE=9600
ENV GPS_ZMQ_ADDRESS=tcp://0.0.0.0:5557
ENV GPS_API_PORT=8080
ENV GPS_API_HOST=0.0.0.0

EXPOSE 5557
EXPOSE 8080

CMD ["gps-server", "--api", "--log-level", "INFO"]
