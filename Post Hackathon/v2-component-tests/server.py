#!/usr/bin/env python3
"""
ESP32 Audio Streaming Server - Cloud Edition

The ESP32 connects OUTBOUND to this server (no local network required).

Ports (all configurable below):
  8080  HTTP  - web UI, SSE stream, status, record/stop
  9000  TCP   - ESP32 raw PCM audio (ESP32 connects here)
  12346 UDP   - ESP32 log messages

Recordings saved to /app/recordings/ (mount a volume to persist).
Standard library only - no pip installs needed.
"""

import base64
import datetime
import json
import logging
import logging.handlers
import os
import queue
import socket
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HTTP_PORT    = 8080
ESP32_PORT   = 9000    # ESP32 connects here
UDP_LOG_PORT = 12346
SAMPLE_RATE  = 16000
CHANNELS     = 1
SAMPLE_WIDTH = 2       # bytes (16-bit)
RECORDINGS_DIR = "/app/recordings"
ESP32_LOG_MAX  = 200

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log = logging.getLogger("mictest")
_log.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")
_fh = logging.handlers.RotatingFileHandler(
    "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
)
_fh.setFormatter(_fmt)
_ch = logging.StreamHandler()
_ch.setFormatter(_fmt)
_log.addHandler(_fh)
_log.addHandler(_ch)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_lock            = threading.Lock()
_esp32_connected = False
_esp32_addr      = None
_bytes_received  = 0
_session_start   = None
_last_chunk_t    = None
_recording       = False
_wav_writer      = None
_wav_filename    = None
_sse_queues      = []
_esp32_logs      = []

# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------
def _add_queue(q):
    with _lock:
        _sse_queues.append(q)

def _remove_queue(q):
    with _lock:
        try:
            _sse_queues.remove(q)
        except ValueError:
            pass

def _broadcast(data: bytes):
    with _lock:
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)

# ---------------------------------------------------------------------------
# Recording helpers (must be called with _lock held)
# ---------------------------------------------------------------------------
def _do_start_recording():
    global _recording, _wav_writer, _wav_filename
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _wav_filename = os.path.join(RECORDINGS_DIR, f"recording_{ts}.wav")
    wf = wave.open(_wav_filename, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(SAMPLE_WIDTH)
    wf.setframerate(SAMPLE_RATE)
    _wav_writer = wf
    _recording = True
    _log.info(f"Recording started: {_wav_filename}")

def _do_stop_recording():
    global _recording, _wav_writer
    _recording = False
    if _wav_writer:
        _wav_writer.close()
        _wav_writer = None
        _log.info(f"Recording saved: {_wav_filename}")

# ---------------------------------------------------------------------------
# ESP32 connection handler
# ---------------------------------------------------------------------------
def _handle_esp32(conn: socket.socket, addr):
    global _esp32_connected, _esp32_addr, _bytes_received, _session_start, _last_chunk_t

    with _lock:
        _esp32_connected = True
        _esp32_addr      = addr[0]
        _bytes_received  = 0
        _session_start   = time.time()
        _last_chunk_t    = time.time()

    conn.settimeout(5)
    try:
        while True:
            try:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                with _lock:
                    _bytes_received += len(chunk)
                    _last_chunk_t    = time.time()
                    total = _bytes_received
                    if _recording and _wav_writer:
                        _wav_writer.writeframes(chunk)
                _broadcast(chunk)
                if total % 32768 < 1024:
                    secs = total / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
                    _log.debug(f"Received {total:,} bytes ({secs:.1f}s)")
            except socket.timeout:
                continue
            except OSError:
                break
    finally:
        with _lock:
            _esp32_connected = False
            _esp32_addr      = None
            if _recording:
                _do_stop_recording()
        conn.close()
        _log.info(f"ESP32 {addr[0]} disconnected")

# ---------------------------------------------------------------------------
# TCP accept loop — waits for ESP32 to connect
# ---------------------------------------------------------------------------
def _tcp_accept_loop():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", ESP32_PORT))
    srv.listen(1)
    _log.info(f"ESP32 TCP listener on port {ESP32_PORT}")
    while True:
        conn, addr = srv.accept()
        _log.info(f"ESP32 connected from {addr[0]}")
        # Runs synchronously — accept loop blocks until connection closes,
        # then immediately waits for the next one.
        threading.Thread(target=_handle_esp32, args=(conn, addr), daemon=True).start()

# ---------------------------------------------------------------------------
# UDP log receiver
# ---------------------------------------------------------------------------
def _udp_log_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", UDP_LOG_PORT))
    _log.info(f"UDP log listener on port {UDP_LOG_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg  = data.decode("utf-8", errors="replace").strip()
            if not msg:
                continue
            ts   = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"{ts}  [ESP32 {addr[0]}]  {msg}"
            _log.info(f"[ESP32 {addr[0]}] {msg}")
            with _lock:
                _esp32_logs.append(line)
                if len(_esp32_logs) > ESP32_LOG_MAX:
                    _esp32_logs.pop(0)
        except Exception as exc:
            _log.warning(f"UDP log error: {exc}")

# ---------------------------------------------------------------------------
# Embedded HTML / JS
# ---------------------------------------------------------------------------
_HTML = b"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Microphone Test</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #111; color: #ddd; font-family: monospace;
    display: flex; flex-direction: column; align-items: center;
    gap: 1.2rem; padding: 2rem; min-height: 100vh;
  }
  h2 { color: #fff; letter-spacing: 0.05em; }
  .controls { display: flex; gap: 0.8rem; align-items: center; flex-wrap: wrap; justify-content: center; }
  button {
    padding: 0.35rem 1rem; font-family: monospace; font-size: 0.9rem;
    border: 1px solid #555; border-radius: 3px; cursor: pointer;
    background: #2a2a2a; color: #eee; transition: background 0.15s;
  }
  button:hover { background: #3a3a3a; }
  button#btnRecord { border-color: #4a4; color: #8f8; }
  button#btnStop   { border-color: #a44; color: #f88; }
  #esp32pill {
    font-size: 0.82rem; padding: 0.25rem 0.7rem;
    border-radius: 99px; border: 1px solid #444; color: #888;
    transition: all 0.3s;
  }
  #esp32pill.connected { border-color: #4a4; color: #8f8; background: #0a1f0a; }
  #recStatus { color: #888; font-size: 0.85rem; }
  canvas {
    background: #000; border: 1px solid #2a2a2a;
    width: 100%; max-width: 860px; height: 200px; border-radius: 4px;
  }
  .hint { color: #555; font-size: 0.78rem; }
  .panels { display: flex; gap: 1rem; width: 100%; max-width: 860px; flex-wrap: wrap; }
  .panel {
    flex: 1; min-width: 260px; background: #161616;
    border: 1px solid #2a2a2a; border-radius: 4px; padding: 0.6rem;
  }
  .panel h3 { color: #aaa; font-size: 0.8rem; margin-bottom: 0.5rem;
               letter-spacing: 0.08em; text-transform: uppercase; }
  #statsTable { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  #statsTable td { padding: 0.2rem 0.4rem; }
  #statsTable td:first-child { color: #666; width: 55%; }
  #statsTable td:last-child  { color: #ccc; }
  #logBox {
    height: 160px; overflow-y: auto; font-size: 0.75rem; line-height: 1.5;
    color: #8bc; white-space: pre-wrap; word-break: break-all;
  }
  #logBox .err { color: #f88; }
</style>
</head>
<body>
<h2>Microphone Test</h2>

<div class="controls">
  <span id="esp32pill">ESP32: waiting...</span>
  <button id="btnRecord" onclick="startRec()">Record</button>
  <button id="btnStop"   onclick="stopRec()">Stop</button>
  <span id="recStatus"></span>
</div>

<canvas id="waveform"></canvas>
<div class="hint">Live waveform - auto-connects when ESP32 is streaming</div>

<div class="panels">
  <div class="panel">
    <h3>Status</h3>
    <table id="statsTable">
      <tr><td>ESP32</td><td id="sConn">-</td></tr>
      <tr><td>Bytes received</td><td id="sBytes">-</td></tr>
      <tr><td>Duration</td><td id="sDuration">-</td></tr>
      <tr><td>SSE subscribers</td><td id="sSse">-</td></tr>
      <tr><td>Last chunk age</td><td id="sChunk">-</td></tr>
      <tr><td>Recording</td><td id="sRec">-</td></tr>
    </table>
  </div>
  <div class="panel" style="flex:2">
    <h3>ESP32 Logs</h3>
    <div id="logBox"></div>
  </div>
</div>

<script>
const canvas   = document.getElementById('waveform');
const ctx      = canvas.getContext('2d');

const DISP    = 8000;
const ringBuf = new Int16Array(DISP);
let   head    = 0;

function pushSamples(s16) {
  for (let i = 0; i < s16.length; i++) {
    ringBuf[head % DISP] = s16[i];
    head++;
  }
}

function resizeCanvas() {
  const r = canvas.getBoundingClientRect();
  if (canvas.width !== r.width || canvas.height !== r.height) {
    canvas.width = r.width; canvas.height = r.height;
  }
}

function drawWaveform() {
  resizeCanvas();
  const W = canvas.width, H = canvas.height;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#1a1a1a'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, H/2); ctx.lineTo(W, H/2); ctx.stroke();
  ctx.strokeStyle = '#00cc66'; ctx.lineWidth = 1.5;
  ctx.beginPath();
  const total    = Math.min(head, DISP);
  const startIdx = head > DISP ? head - DISP : 0;
  for (let x = 0; x < W; x++) {
    const idx = Math.floor(startIdx + (x / W) * total) % DISP;
    const s   = ringBuf[idx] / 32768;
    const y   = H / 2 - s * (H / 2 - 6);
    x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.stroke();
  requestAnimationFrame(drawWaveform);
}
requestAnimationFrame(drawWaveform);

// Auto-connect SSE on load
const evtSrc = new EventSource('stream');
evtSrc.onmessage = e => {
  const bin = atob(e.data);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  pushSamples(new Int16Array(buf.buffer));
};

function startRec() {
  fetch('record').then(r => r.text()).then(t => {
    document.getElementById('recStatus').textContent = t;
  });
}
function stopRec() {
  fetch('stop').then(r => r.text()).then(t => {
    document.getElementById('recStatus').textContent = t;
  });
}

// Status polling
let lastLogLen = 0;
function pollStatus() {
  fetch('status').then(r => r.json()).then(s => {
    const pill = document.getElementById('esp32pill');
    if (s.esp32_connected) {
      pill.textContent = 'ESP32: ' + s.esp32_addr;
      pill.className   = 'connected';
    } else {
      pill.textContent = 'ESP32: waiting...';
      pill.className   = '';
    }
    document.getElementById('sConn').textContent     = s.esp32_connected ? s.esp32_addr : 'disconnected';
    document.getElementById('sBytes').textContent    = s.bytes_received.toLocaleString() + ' B';
    document.getElementById('sDuration').textContent = s.duration_s.toFixed(1) + ' s';
    document.getElementById('sSse').textContent      = s.sse_subscribers;
    document.getElementById('sChunk').textContent    = s.last_chunk_age_ms !== null ? s.last_chunk_age_ms + ' ms' : '-';
    document.getElementById('sRec').textContent      = s.recording ? 'YES' : 'no';

    const box  = document.getElementById('logBox');
    const logs = s.esp32_logs || [];
    if (logs.length > lastLogLen) {
      logs.slice(lastLogLen).forEach(line => {
        const span = document.createElement('span');
        span.className   = /error|fail|err/i.test(line) ? 'err' : '';
        span.textContent = line + '\\n';
        box.appendChild(span);
      });
      box.scrollTop  = box.scrollHeight;
      lastLogLen = logs.length;
    }
  }).catch(() => {});
}
setInterval(pollStatus, 2000);
pollStatus();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):

    def log_message(self, _fmt, *args):
        if int(args[1]) >= 400:
            _log.warning(f"HTTP {args[1]} {args[0]}")

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code: int, msg: str):
        self._send(code, "text/plain", msg.encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/":
            self._send(200, "text/html; charset=utf-8", _HTML)

        elif path == "/record":
            with _lock:
                if not _esp32_connected:
                    self._text(409, "ESP32 not connected")
                    return
                if _recording:
                    self._text(409, "already recording")
                    return
                _do_start_recording()
            self._text(200, f"recording started")

        elif path == "/stop":
            with _lock:
                if not _recording:
                    self._text(409, "not recording")
                    return
                _do_stop_recording()
            self._text(200, "recording stopped")

        elif path == "/stream":
            q = queue.Queue(maxsize=64)
            _add_queue(q)
            self.send_response(200)
            self.send_header("Content-Type",      "text/event-stream")
            self.send_header("Cache-Control",     "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                while True:
                    try:
                        chunk = q.get(timeout=1)
                        b64   = base64.b64encode(chunk).decode()
                        self.wfile.write(f"data: {b64}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b":\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                _remove_queue(q)

        elif path == "/status":
            now = time.time()
            with _lock:
                payload = {
                    "esp32_connected":   _esp32_connected,
                    "esp32_addr":        _esp32_addr,
                    "bytes_received":    _bytes_received,
                    "duration_s":        round(now - _session_start, 1) if _session_start else 0.0,
                    "sse_subscribers":   len(_sse_queues),
                    "last_chunk_age_ms": int((now - _last_chunk_t) * 1000) if _last_chunk_t else None,
                    "recording":         _recording,
                    "esp32_logs":        list(_esp32_logs),
                }
            self._send(200, "application/json", json.dumps(payload).encode())

        else:
            self._text(404, "not found")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=_tcp_accept_loop, daemon=True).start()
    threading.Thread(target=_udp_log_loop,    daemon=True).start()

    server = ThreadingHTTPServer(("", HTTP_PORT), _Handler)
    _log.info(f"HTTP server on port {HTTP_PORT}")
    _log.info(f"ESP32 TCP listener on port {ESP32_PORT}")
    _log.info(f"UDP log listener on port {UDP_LOG_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log.info("Shutting down.")
        server.server_close()
