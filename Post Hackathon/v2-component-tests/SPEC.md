# XIAO ESP32C3 + INMP441 Audio Streaming Test

## Hardware

### RC522 RFID Reader — SPI

The RC522 uses SPI, a 4-wire synchronous bus. Any microcontroller with a hardware SPI peripheral works; the pin names below are the logical SPI signals, not physical pin numbers.

| RC522 Pin | Signal | XIAO Pin | Why |
|-----------|--------|----------|-----|
| SDA | SPI Slave Select (SS/CS) | D3 (GPIO4) | Pulled low to select this device on the bus; any GPIO works |
| SCK | SPI Clock | D8 (GPIO8) | Hardware SPI clock — use the MCU's dedicated SCK pin for best performance |
| MOSI | Master Out Slave In | D10 (GPIO10) | Data from MCU to RC522 — hardware SPI MOSI pin |
| MISO | Master In Slave Out | D9 (GPIO9) | Data from RC522 to MCU — hardware SPI MISO pin |
| RST | Reset | D2 (GPIO0) | Active-low reset; any GPIO works |
| 3.3V | Power | 3.3V | RC522 is a 3.3V device — do not use 5V |
| GND | Ground | GND | Common ground |

> The RC522 must be powered at 3.3V. It is **not** 5V tolerant.

---

### INMP441 Microphone — I2S

The INMP441 uses I2S, a 3-wire serial audio bus (clock, word select, data). On ESP32 the I2S signals can be mapped to any GPIO via the internal GPIO matrix — the choices below are simply free pins that don't conflict with SPI. On other microcontrollers, check whether I2S pins are fixed or flexible.

| INMP441 Pin | Signal | XIAO Pin | Why |
|-------------|--------|----------|-----|
| VDD | Power | 3.3V | INMP441 runs at 1.8–3.3V; 3.3V is the safe choice |
| GND | Ground | GND | Common ground |
| SCK | Bit Clock (BCLK) | D5 (GPIO7) | I2S serial clock — drives the bit rate; any I2S-capable GPIO on ESP32 |
| WS | Word Select (LRCK) | D1 (GPIO3) | Toggles each audio frame to indicate left vs right channel; any I2S-capable GPIO |
| SD | Serial Data | D0 (GPIO2) | Audio data output from the mic into the MCU; any I2S-capable GPIO |
| L/R | Channel Select | GND | Tied to GND = mic outputs on the **left** channel. Tie to 3.3V for right channel. Must match the channel format configured in firmware (`I2S_CHANNEL_FMT_ONLY_LEFT` in our sketch) |

> **Porting to another MCU:** You need a peripheral that supports I2S in master-receive mode (MCU generates BCLK and WS, mic outputs SD). Common alternatives: RP2040 (PIO-based I2S), STM32 (SAI or I2S peripheral), nRF52840 (I2S peripheral). The signal names — BCLK, LRCK/WS, SD — are standard across all of them.

---

## Arduino Sketch (ESP32 Arduino framework)

Extend the existing RFID sketch to also:

- Connect to WiFi on boot and print the assigned IP to serial
- Continuously read I2S audio from the INMP441 at 16kHz, 16-bit mono using the ESP32 Arduino I2S library
- Print a basic VU meter value to serial (RMS or peak of each buffer)
- Listen on TCP port 12345; when a client connects, stream raw 16-bit PCM audio until the client disconnects
- After disconnect, go back to listening for new connections
- RFID reading should continue working independently — use a non-blocking approach so both work concurrently (no RTOS needed, just interleave in `loop()`)

WiFi credentials should be defined as constants at the top of the file:

```cpp
#define WIFI_SSID "your_ssid"
#define WIFI_PASS "your_password"
#define SERVER_PORT 12345
```

---

## Python Server (WSL or Windows)

A single Python script (`server.py`) with no external dependencies (standard library only). It runs two services concurrently using threads:

### HTTP server — port 8080

Serves a web UI and a small control API:

| Route | Description |
|-------|-------------|
| `GET /` | Serves the HTML page |
| `GET /start?ip=<esp32_ip>` | Connects to the ESP32 TCP server and begins streaming |
| `GET /stop` | Disconnects from the ESP32 |
| `GET /stream` | Server-Sent Events endpoint — pushes audio chunks to the browser |

### TCP client — connects to ESP32 on demand

- On `/start`, opens a TCP connection to `<esp32_ip>:12345`
- Reads raw 16-bit little-endian mono PCM at 16kHz in chunks
- Simultaneously:
  - Writes chunks to a `recording.wav` file (using Python's `wave` module)
  - Queues base64-encoded chunks for the `/stream` SSE endpoint
- On `/stop` or connection drop, finalizes the WAV file and prints the output path
- Prints bytes-received progress to console

### Web UI

Single-page app embedded in the Python script as an HTML string. Features:

- Input field for the ESP32 IP address
- Start / Stop buttons that call `/start` and `/stop`
- Live waveform canvas that subscribes to `/stream` (SSE), decodes each base64 PCM chunk, and renders a scrolling oscilloscope-style waveform using the Canvas API
- No external JS libraries — plain browser APIs only (Canvas 2D, EventSource, Fetch)

---

## Testing Flow

1. Start `server.py` in WSL
2. Open `http://localhost:8080` in a browser on Windows
3. Power on the XIAO — it connects to WiFi and prints its IP to serial
4. Enter the ESP32 IP in the web UI and click Start
5. Watch the live waveform; speak into the mic to verify it responds
6. Click Stop — `recording.wav` is finalized
7. Open `recording.wav` on Windows and listen

---

## Notes

- The XIAO C3 has ~400KB RAM so keep the I2S DMA buffer small (e.g. 512 or 1024 samples) and stream directly rather than buffering the whole recording
- The ESP32 Arduino I2S library uses `i2s_read()` style calls — use `I2S_NUM_0`
- SSE (`text/event-stream`) is a plain HTTP chunked response — no WebSocket library needed
- WSL IP can be found with `hostname -I` in WSL; Windows firewall may need a rule to allow inbound TCP on port 8080 if accessing from another machine (localhost forwarding usually works for same-machine browser access)
- Each `/stream` SSE connection should get its own queue fed from the shared audio thread so multiple browser tabs work independently
- `recording.wav` is written to the working directory; timestamp the filename if you want to keep multiple recordings
