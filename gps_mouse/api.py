"""FastAPI REST + WebSocket + live map dashboard.

Requires: pip install gps-mouse[api]

Usage:
    from gps_mouse import GPSReader
    from gps_mouse.api import GPSApi

    reader = GPSReader()
    api = GPSApi(reader)
    reader.start()
    api.serve()          # blocks — runs on http://0.0.0.0:8080

Or from CLI:
    gps-api --host 0.0.0.0 --port 8080

Endpoints:
    GET  /           → live map dashboard
    GET  /gps        → latest fix (JSON)
    GET  /gps/stream → Server-Sent Events stream
    WS   /gps/ws     → WebSocket stream
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .reader import GPSReader

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Dashboard HTML (self-contained, no external files needed)
# ------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GPS Mouse — Live Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: monospace; background: #1a1a2e; color: #eee; display: flex; flex-direction: column; height: 100vh; }
  #header { padding: 10px 16px; background: #16213e; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid #0f3460; }
  #header h1 { font-size: 1rem; color: #e94560; }
  #status { font-size: 0.8rem; color: #aaa; }
  #status span { color: #4ecca3; }
  #info { display: flex; gap: 12px; font-size: 0.75rem; flex-wrap: wrap; }
  .badge { background: #0f3460; padding: 3px 8px; border-radius: 4px; }
  .badge b { color: #4ecca3; }
  #map { flex: 1; }
  #nofix { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
           background: #e9456088; padding: 12px 24px; border-radius: 8px; font-size: 1.2rem;
           pointer-events: none; z-index: 999; }
</style>
</head>
<body>
<div id="header">
  <h1>🛰 GPS Mouse</h1>
  <div id="status">Status: <span id="conn">connecting…</span></div>
  <div id="info">
    <div class="badge">Lat: <b id="lat">---</b></div>
    <div class="badge">Lon: <b id="lon">---</b></div>
    <div class="badge">Alt: <b id="alt">---</b></div>
    <div class="badge">Speed: <b id="spd">---</b></div>
    <div class="badge">Heading: <b id="hdg">---</b></div>
    <div class="badge">Sats: <b id="sats">---</b></div>
    <div class="badge">HDOP: <b id="hdop">---</b></div>
  </div>
</div>
<div id="map"></div>
<div id="nofix">NO FIX</div>

<script>
const map = L.map('map', { zoomControl: true }).setView([39.9, 32.6], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors', maxZoom: 19
}).addTo(map);

const marker = L.marker([39.9, 32.6]).addTo(map);
const trail = L.polyline([], { color: '#4ecca3', weight: 2, opacity: 0.7 }).addTo(map);
const MAX_TRAIL = 200;
let firstFix = true;

function update(d) {
  document.getElementById('conn').textContent = 'connected';
  document.getElementById('sats').textContent = d.num_satellites;
  document.getElementById('hdop').textContent = d.hdop != null ? d.hdop.toFixed(1) : '---';

  if (d.latitude == null) {
    document.getElementById('nofix').style.display = 'block';
    return;
  }
  document.getElementById('nofix').style.display = 'none';

  const lat = d.latitude, lon = d.longitude;
  document.getElementById('lat').textContent = lat.toFixed(6);
  document.getElementById('lon').textContent = lon.toFixed(6);
  document.getElementById('alt').textContent = d.altitude != null ? d.altitude.toFixed(1) + ' m' : '---';
  document.getElementById('spd').textContent = d.speed != null ? (d.speed * 3.6).toFixed(1) + ' km/h' : '---';
  document.getElementById('hdg').textContent = d.heading != null ? d.heading.toFixed(1) + '°' : '---';

  marker.setLatLng([lat, lon]);
  const pts = trail.getLatLngs();
  pts.push([lat, lon]);
  if (pts.length > MAX_TRAIL) pts.shift();
  trail.setLatLngs(pts);

  if (firstFix) { map.setView([lat, lon], 16); firstFix = false; }
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/gps/ws`);
  ws.onopen  = () => document.getElementById('conn').textContent = 'connected';
  ws.onmessage = e => update(JSON.parse(e.data));
  ws.onclose = () => {
    document.getElementById('conn').textContent = 'reconnecting…';
    setTimeout(connect, 2000);
  };
}
connect();
</script>
</body>
</html>
"""


class GPSApi:
    """FastAPI-based GPS server with REST, WebSocket, and live map.

    Args:
        reader: GPSReader instance (must be started separately)
        host:   Bind host (default 0.0.0.0)
        port:   Bind port (default 8080)
    """

    def __init__(self, reader: "GPSReader", host: str = "0.0.0.0", port: int = 8080) -> None:
        self.reader = reader
        self.host = host
        self.port = port
        self._app = None
        self._ws_clients: list = []

    # ------------------------------------------------------------------
    # Build FastAPI app
    # ------------------------------------------------------------------

    def build_app(self):
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import HTMLResponse, StreamingResponse
        except ImportError:
            raise ImportError("FastAPI is required: pip install gps-mouse[api]")

        app = FastAPI(title="GPS Mouse API", version="0.1.1")

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return HTMLResponse(_DASHBOARD_HTML)

        @app.get("/gps")
        async def current():
            return self.reader.last.to_dict()

        @app.get("/gps/stream")
        async def sse_stream():
            async def generator():
                q: asyncio.Queue = asyncio.Queue(maxsize=50)
                self.reader._queues.append(q)
                try:
                    while True:
                        data = await q.get()
                        yield f"data: {data.to_json()}\n\n"
                finally:
                    self.reader._queues.remove(q)
            return StreamingResponse(generator(), media_type="text/event-stream")

        @app.websocket("/gps/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            q: asyncio.Queue = asyncio.Queue(maxsize=50)
            self.reader._queues.append(q)
            try:
                while True:
                    data = await q.get()
                    await websocket.send_text(data.to_json())
            except WebSocketDisconnect:
                pass
            finally:
                if q in self.reader._queues:
                    self.reader._queues.remove(q)

        self._app = app
        return app

    # ------------------------------------------------------------------
    # Serve (blocking)
    # ------------------------------------------------------------------

    def serve(self) -> None:
        try:
            import uvicorn
        except ImportError:
            raise ImportError("uvicorn is required: pip install gps-mouse[api]")

        app = self.build_app()
        logger.info("GPS API starting at http://%s:%d", self.host, self.port)
        uvicorn.run(app, host=self.host, port=self.port, log_level="warning")
