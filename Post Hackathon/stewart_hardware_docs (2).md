# Stewart — Hardware Technical Documentation

**Community Sharing Station | Team Minions — Connect Track**
**Last updated:** March 2026 | **Hardware Lead:** Max | **Status:** Pre-prototype

---

## How to Use This Document

This is the living technical reference for Stewart's hardware. It covers every component, why it's here, how it connects, and how to test it. If you're touching hardware, start here.

**For software folks:** Jump to [§5 WebSocket Protocol](#5-websocket-protocol--firmware-architecture) and [§6 Cloud Integration](#6-cloud-integration-notes) — that's where hardware meets your world.

**For hardware folks:** [§3 Wiring](#3-wiring--pin-assignments) and [§4 Power Budget](#4-power-budget) are your primary references.

**To simulate before building:** See [§7 Simulation & Testing](#7-simulation--testing).

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Component Reference](#2-component-reference)
3. [Wiring & Pin Assignments](#3-wiring--pin-assignments)
4. [Power Budget](#4-power-budget)
5. [WebSocket Protocol & Firmware Architecture](#5-websocket-protocol--firmware-architecture)
6. [Cloud Integration Notes](#6-cloud-integration-notes)
7. [Simulation & Testing](#7-simulation--testing)
8. [Physical Enclosure & Assembly](#8-physical-enclosure--assembly)
9. [BOM & Procurement Tracker](#9-bom--procurement-tracker)
10. [Known Issues & Gotchas](#10-known-issues--gotchas)
11. [Changelog](#11-changelog)

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     STEWART (1 unit)                         │
│                                                             │
│  ┌─────────────┐    I2S     ┌───────────┐                  │
│  │  ICS-43434  │──────────►│            │    WiFi/WS       │
│  │  Microphone │           │  ESP32-S3  │◄──────────────►  Cloud
│  └─────────────┘           │   CAM      │                  │
│                            │            │    I2S            │
│  ┌─────────────┐           │  (Brain)   │──────────────►   │
│  │  OV2640 /   │  Parallel │            │           ┌──────┤
│  │  OV5640 Cam │──────────►│            │           │MAX   │
│  └─────────────┘           │            │           │98357A│
│                            └─────┬──┬───┘           │ Amp  │
│  ┌─────────────┐          GPIO│  │GPIO    ┌────────┤      │
│  │ PIR Sensor  │──────────────┘  │        │Speaker │      │
│  │ (wake)      │                 │        └────────┘──────┘
│  └─────────────┘                 │
│                            GPIO  │  GPIO
│  ┌─────────────┐    ┌───────────┴──────────────┐          │
│  │ WS2812B     │◄───┤                          │          │
│  │ NeoPixels   │    │     ┌──────────┐         │          │
│  └─────────────┘    │     │ MOSFET   │         │          │
│                     │     │ + Diode  │         │          │
│                     │     └────┬─────┘         │          │
│                     │          │ 12V            │          │
│                     │     ┌────┴─────┐         │          │
│                     │     │ Solenoid │         │          │
│                     │     │ Lock     │         │          │
│                     │     └──────────┘         │          │
│                     │                          │          │
│  ┌──────────────────┴──────────────────────────┘          │
│  │  Power: 5V USB-C → ESP32 + peripherals                 │
│  │         5V → MT3608 boost → 12V → Solenoid             │
│  │  (or: Solar panel → CN3791 → LiPo → same)             │
│  └────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘

Cloud Stack:
  Phone (NFC auth) → Vercel (React TSX) → Supabase (DB/auth)
                                         → Anthropic (vision, conversation)
                                         → ElevenLabs (voice synthesis)
```

### Interaction Flow (Happy Path)

1. **Person walks up** → PIR sensor triggers → ESP32 wakes from light sleep
2. **ESP32 opens WebSocket** to cloud backend (or reconnects if already open)
3. **NeoPixels animate** welcome pattern → cloud sends greeting audio
4. **Person taps phone (NFC)** → phone authenticates via cloud → cloud tells ESP32 "user: Alice"
5. **ESP32 fires solenoid** → door pops open (spring-loaded)
6. **White LEDs turn on** inside box → camera takes snapshot
7. **Person places/removes item** → camera takes another snapshot → sent to Anthropic vision
8. **Voice conversation** happens: mic streams audio → cloud → ElevenLabs response → speaker
9. **Person closes door** → solenoid re-locks (spring return) → NeoPixels go idle
10. **After timeout** → ESP32 returns to light sleep

---

## 2. Component Reference

### 2.1 Brain: ESP32-S3 CAM Board (Freenove)

| Spec | Value |
|------|-------|
| MCU | ESP32-S3 (dual-core Xtensa LX7, 240 MHz) |
| Flash | 8 or 16 MB |
| PSRAM | 8 MB |
| WiFi | 802.11 b/g/n, 2.4 GHz, 40 MHz bandwidth |
| Bluetooth | 5.0 LE |
| Camera interface | DVP (parallel), supports OV2640/OV5640 |
| I2S | 2 independent peripherals (one for mic, one for speaker) |
| GPIO | ~36 pins total, ~15-20 available after camera |
| USB | Dual USB-C (OTG + UART) |
| SD card | SDMMC interface, supports SDHC/SDXC (tested up to 32GB+) |

**Why this board:** It's the only sub-$20 board that combines an ESP32-S3 (which has the I2S and camera peripherals we need), a camera connector, WiFi, and enough free GPIOs for all our modules. The Freenove version specifically has good documentation, dual USB-C for easy programming, and a 1GB SD card included.

**Why ESP32-S3 and not ESP32:** The S3 has native USB-OTG, more GPIO pins, and better AI acceleration (not that we use it on-device, but future-proofing). Both the S3 and base ESP32 have 2 I2S peripherals, but the S3's I2S driver supports newer features like TDM mode and the LCD/camera interface shares DMA more cleanly with I2S on the S3.

### 2.2 Cameras

#### OV2640 (included with board)
- 2 megapixel, fixed focus
- JPEG compression on-chip
- Good enough for book cover / board game identification
- Use this for MVP

#### OV5640 (upgrade, ~$10)
- 5 megapixel, **autofocus**
- Better low-light sensitivity
- Same 24-pin FFC connector, drop-in swap
- Use this if OV2640 images aren't sharp enough for Anthropic vision API

**Important:** Image quality depends more on lighting than sensor. Mount 2-3 bright white LEDs inside the box pointing at the item area. A well-lit OV2640 beats a dim OV5640.

### 2.3 Audio Input: ICS-43434 Microphone

| Spec | Value |
|------|-------|
| Type | MEMS, digital, omnidirectional |
| Interface | I2S (24-bit) |
| SNR | 65 dB(A) |
| Frequency response | 50 Hz – 15 kHz |
| Current draw | 490 µA normal, 230 µA low-power |
| Voltage | 1.6 – 3.6V (NOT 5V tolerant) |

**Why this over INMP441:** 4 dB better signal-to-noise ratio. Sounds small, but it's perceptible — cleaner voice capture means fewer transcription errors from Anthropic and better voice activity detection. Also has a built-in low-pass filter that cuts frequencies above 24 kHz, reducing aliasing noise.

**Backup: INMP441** (~$3). Same I2S interface, 61 dB SNR. Good for testing and as a spare. If budget is tight, this is fine.

### 2.4 Audio Output: MAX98357A Amplifier + Speaker

**MAX98357A:**
- I2S input → analog + amplification in one chip
- 3.2W into 4Ω at 5V, 1.8W into 8Ω
- No external DAC or filtering needed
- Runs on 2.7 – 5.5V

**Speaker:** 3-inch, 4Ω, 3W driver
- Larger driver = fuller, warmer sound for voice
- Mount in a sealed chamber inside the enclosure for better bass response

**Why I2S for audio (not analog):** The ESP32-S3 doesn't have a great DAC for audio output. I2S is digital all the way to the MAX98357A, which means no analog noise, no ground loop hum, and cleaner audio. The ElevenLabs voice output will sound noticeably better.

### 2.5 Lock: 12V Solenoid + MOSFET + Diode

**Solenoid lock:**
- 12V DC, 500-600 mA when energized
- Spring-return: locked by default, unlocks when powered
- Only energized for 1-2 seconds per interaction
- **CRITICAL: Do not energize for >20 seconds — coil will overheat**

**IRLZ44N MOSFET:**
- Logic-level: triggers fully at 3.3V gate voltage (compatible with ESP32)
- Switches up to 47A (massive overkill, but cheap and available)
- Sits between ESP32 GPIO and solenoid's 12V power

**1N4007 Flyback diode:**
- Absorbs the voltage spike when solenoid de-energizes
- **Without this, the back-EMF spike WILL damage the MOSFET and potentially the ESP32**
- Wired in reverse-parallel across the solenoid (cathode to +12V, anode to ground)

**Why electric lock and not 3D printed latch:** Reliability. A solenoid is a proven mechanism for cabinet applications. It fails locked (safe default). A 3D printed latch introduces mechanical wear, print quality variance, and weather sensitivity. We can always revisit for v2.

### 2.6 Lights: WS2812B NeoPixel Strip + White LEDs

**WS2812B NeoPixels:**
- Addressable RGB LEDs, single data wire
- 60 LEDs/meter, cut to length (probably 10-15 LEDs for our box)
- Each LED: up to 60 mA at full white, but we'll run at low-medium brightness (~10-20 mA avg)
- Uses ESP32-S3's RMT peripheral — no CPU overhead

**Uses:**
- Status indication: green = ready, blue pulsing = listening, red = error
- Item position: light up specific LEDs to show where to place items
- Welcome animation when person approaches

**White LEDs (3-5 pieces):**
- Simple 5mm LEDs with 330Ω current-limiting resistors
- Mounted inside box, pointed at item area
- Turn on when door opens for camera illumination
- Driven directly from GPIO through resistors (~15 mA each)

### 2.7 Sensor: HC-SR501 PIR Motion Sensor

| Spec | Value |
|------|-------|
| Detection range | ~3-7 meters, 120° cone |
| Output | Digital HIGH (3.3V) when motion detected |
| Quiescent current | ~65 µA |
| Trigger modes | Single trigger (L) or repeatable (H) |
| Adjustable | Sensitivity and hold time via onboard pots |

**Why PIR and not ultrasonic/radar:** Lowest power consumption of any proximity detection method. It draws practically nothing in standby, which matters for our solar-powered use case. Also simple — one digital pin, no libraries needed.

### 2.8 Power Components

**MT3608 Boost Converter (5V → 12V):**
- Steps up the 5V system voltage to 12V for the solenoid
- Adjustable output (set via trimpot, set once and forget)
- Can handle up to 2A output (we need ~0.6A for solenoid)
- **Set this BEFORE connecting the solenoid. Measure with multimeter first.**

**1000 µF Capacitor (16V rated):**
- Sits on the 12V output rail
- Acts as energy reservoir during solenoid pulse
- Prevents voltage sag that could brown out the boost converter
- **Polarity matters: negative stripe to ground, long leg to +12V**

**Solar option (CN3791 + LiPo + panel):**
- CN3791 board: MPPT-style solar charge controller. Manages panel → battery safely.
- 3.7V 5000mAh LiPo: ~18.5 Wh capacity. Provides ~1 week buffer.
- 5-10W 6V solar panel: Produces 10-30 Wh/day depending on season.
- Only needed for off-grid deployments. Indoor units use USB-C wall adapter.

---

## 3. Wiring & Pin Assignments

### 3.1 Pin Map (Freenove ESP32-S3 CAM Board)

**Camera (pre-wired on board — DO NOT reassign these):**

| Function | GPIO |
|----------|------|
| CAM_D0 | GPIO11 |
| CAM_D1 | GPIO9 |
| CAM_D2 | GPIO8 |
| CAM_D3 | GPIO10 |
| CAM_D4 | GPIO12 |
| CAM_D5 | GPIO18 |
| CAM_D6 | GPIO17 |
| CAM_D7 | GPIO16 |
| CAM_XCLK | GPIO15 |
| CAM_PCLK | GPIO13 |
| CAM_VSYNC | GPIO6 |
| CAM_HREF | GPIO7 |
| CAM_SDA | GPIO4 |
| CAM_SCL | GPIO5 |
| CAM_PWDN | GPIO-1 (not used) |
| CAM_RESET | GPIO-1 (not used) |

**Available GPIOs for our modules:**

| GPIO | Assigned To | Interface | Notes |
|------|------------|-----------|-------|
| GPIO1 | ICS-43434 BCLK | I2S0 CLK | Mic bit clock |
| GPIO2 | ICS-43434 WS | I2S0 WS | Mic word select |
| GPIO3 | ICS-43434 SD | I2S0 DIN | Mic data |
| GPIO38 | MAX98357A BCLK | I2S1 CLK | Speaker bit clock |
| GPIO39 | MAX98357A LRC | I2S1 WS | Speaker word select |
| GPIO40 | MAX98357A DIN | I2S1 DOUT | Speaker data |
| GPIO41 | WS2812B Data | RMT | NeoPixel strip |
| GPIO42 | Solenoid MOSFET Gate | Digital OUT | Lock control |
| GPIO14 | PIR Sensor Output | Digital IN | Wake trigger (RTC GPIO — required for ext0 deep sleep wake) |
| GPIO47 | White LEDs (via NPN transistor) | Digital OUT | Interior lights (transistor required — see §2.6) |
| GPIO48 | (spare) | — | Future use |
| GPIO46 | **DO NOT USE** | — | Boot strap pin on ESP32-S3. Directly driving it can prevent boot. |

**IMPORTANT:** These pin assignments are preliminary. Verify against the specific Freenove board revision you receive. Some GPIOs may be used internally for flash/PSRAM (especially GPIO26-32 on WROOM modules with octal PSRAM).

### 3.2 Wiring Diagram — Microphone (ICS-43434)

```
ICS-43434          ESP32-S3
─────────          ────────
VDD  ──────────── 3.3V
GND  ──────────── GND
BCLK ──────────── GPIO1
WS   ──────────── GPIO2
SD   ──────────── GPIO3
L/R  ──────────── GND (left channel) or 3.3V (right channel)
```

**Notes:**
- Power with 3.3V ONLY. This mic is NOT 5V tolerant.
- L/R pin selects stereo channel. Tie to GND for left. If using two mics for stereo, one to GND, one to 3.3V.
- Keep wires short (<10cm) to minimize I2S signal noise.

### 3.3 Wiring Diagram — Speaker (MAX98357A)

```
MAX98357A          ESP32-S3
──────────         ────────
VIN  ──────────── 5V (or 3.3V for quieter output)
GND  ──────────── GND
BCLK ──────────── GPIO38
LRC  ──────────── GPIO39
DIN  ──────────── GPIO40
GAIN ──────────── (leave unconnected = 9dB default)
SD   ──────────── (leave unconnected = always on)

Speaker (4Ω 3W):
  + ──────────── MAX98357A (+) terminal
  - ──────────── MAX98357A (-) terminal
```

**Notes:**
- GAIN pin: unconnected = 9dB. Tie to GND = 12dB. Tie to VIN = 15dB. Start with default.
- SD (shutdown) pin: unconnected = always on. Pull LOW to shutdown (saves power when not speaking).
- If you hear crackling, try powering from 3.3V instead of 5V — 5V can cause clipping on some speakers.

### 3.4 Wiring Diagram — Solenoid Lock

```
                    12V rail (from MT3608 boost converter)
                         │
                    ┌────┴────┐
                    │         │
                    │ 1000µF  │  (electrolytic capacitor, 16V rated)
                    │ CAP     │  (long leg = +, stripe = -)
                    │         │
                    └────┬────┘
                         │
          ┌──────────────┤
          │              │
     ┌────┴────┐    ┌────┴────┐
     │ DIODE   │    │ SOLENOID│
     │ 1N4007  │    │  LOCK   │
     │ (band   │    │         │
     │  toward │    │         │
     │  +12V)  │    │         │
     └────┬────┘    └────┬────┘
          │              │
          └──────┬───────┘
                 │
            ┌────┴────┐
            │ MOSFET  │
            │ IRLZ44N │
            │         │
            │ D (top) │ ← connected to solenoid/diode junction
            │ G (left)│ ← GPIO42 on ESP32
            │ S (right│ ← GND
            └─────────┘
                 │
                GND (common ground with ESP32)

MT3608 Boost Converter:
  VIN+  ──── 5V (from USB-C or LiPo)
  VIN-  ──── GND
  VOUT+ ──── 12V rail (to solenoid circuit above)
  VOUT- ──── GND
```

**CRITICAL NOTES:**
1. **Set the MT3608 output to 12V BEFORE connecting the solenoid.** Use a multimeter. Turn the trimpot slowly.
2. **Diode orientation matters.** The cathode band (silver stripe) faces toward +12V. If reversed, the diode shorts out your power supply.
3. **Common ground.** The ESP32 GND, MOSFET source, and 12V rail GND must all be connected together.
4. **Never hold the solenoid on for >20 seconds.** In firmware, add a hard timeout.

### 3.5 Wiring Diagram — NeoPixels + PIR + White LEDs

```
WS2812B Strip:
  VCC (red)  ──── 5V
  GND (white) ── GND
  DIN (green) ── GPIO41 (with 330Ω resistor in series, close to ESP32 pin)

PIR Sensor (HC-SR501):
  VCC ──── 5V (some modules need 5V minimum)
  GND ──── GND
  OUT ──── GPIO14 (RTC-capable GPIO — required for deep sleep wake)

White LEDs (x3, parallel, transistor-switched):
  GPIO47 ── 1KΩ resistor ── Base of 2N2222 NPN transistor
  Collector ── LED1 anode ── 330Ω ── 5V
               LED2 anode ── 330Ω ── 5V
               LED3 anode ── 330Ω ── 5V
  Emitter ──── GND

  NOTE: Do NOT drive multiple LEDs directly from a GPIO pin.
  ESP32-S3 GPIOs are rated for max 40mA. Three LEDs at 15mA each
  (45mA) exceeds this. Always use a transistor or MOSFET to switch
  LED power from the 5V rail.
```

---

## 4. Power Budget

### 4.1 State-by-State Power Draw

All values expressed as current draw from the **5V input rail**. The solenoid draws 500mA at 12V, but the boost converter pulls that from the 5V rail at ~1.4A (accounting for ~85% converter efficiency: 6W / 5V / 0.85 ≈ 1.4A).

| State | ESP32-S3 | Camera | Mic | Amp+Speaker | LEDs | Solenoid (at 5V input) | PIR | **Total from 5V** |
|-------|----------|--------|-----|-------------|------|----------------------|-----|-------------------|
| Deep sleep | 10 µA | off | off | off | off | off | 65 µA | **~75 µA** |
| Light sleep (WiFi maintained) | 5 mA | off | off | off | off | off | 65 µA | **~5 mA** |
| Wake + greeting | 240 mA | off | 0.5 mA | 100 mA | 100 mA | off | 65 µA | **~440 mA** |
| Active conversation | 240 mA | off | 0.5 mA | 100 mA | 50 mA | off | 65 µA | **~390 mA** |
| Camera capture (burst) | 240 mA | 120 mA | 0.5 mA | 100 mA | 50 mA | off | 65 µA | **~510 mA** |
| Solenoid firing (1-2 sec) | 240 mA | off | 0.5 mA | 50 mA | 100 mA | ~1400 mA | 65 µA | **~1.8 A peak** |

**IMPORTANT:** The solenoid firing state draws ~1.8A from the 5V supply for 1-2 seconds. Your USB-C adapter or LiPo must handle this burst. A 5V/3A adapter has plenty of headroom. A weak phone charger (5V/1A) will brown out.

### 4.2 Daily Energy Budget

**Assumptions:**
- 10 interactions per day, ~3 minutes each
- Active hours (light sleep): 14 hours (7am - 9pm)
- Deep sleep: 10 hours (9pm - 7am)

| State | Duration/day | Avg power | Energy |
|-------|-------------|-----------|--------|
| Deep sleep | 10 hours | 0.375 mW | 0.004 Wh |
| Light sleep | 13.5 hours | 25 mW | 0.34 Wh |
| Active interactions | 0.5 hours | 2.2 W | 1.1 Wh |
| Solenoid pulses | 20 seconds | 9 W (1.8A × 5V) | 0.05 Wh |
| **DAILY TOTAL** | | | **~1.5 Wh** |

### 4.3 Solar Sizing (Off-Grid Deployments)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Daily consumption | 1.5 Wh | See above |
| Worst-case sun (Cambridge, December) | ~2 effective hours | Overcast, short days |
| Panel needed | 5W minimum | 5W × 2h = 10 Wh (6.7x daily need) |
| Battery for 3 cloudy days | 4.5 Wh minimum | 5000 mAh × 3.7V = 18.5 Wh (plenty) |
| Battery for 7 cloudy days | 10.5 Wh minimum | Same 5000 mAh battery covers this |

**Conclusion:** A 5W panel + 5000 mAh LiPo provides ~12x daily energy needs and >1 week of cloudy buffer. This is very comfortable even for Cambridge winters.

**NOTE on solar + solenoid:** The 1.8A peak solenoid burst is the highest instantaneous draw. The LiPo can deliver this easily (most 5000mAh LiPos are rated for 2-5A continuous). The solar charge controller does NOT need to handle this — the battery buffers it.

### 4.4 Wall Power (Indoor Deployments)

Use a USB-C 5V/3A adapter. Stewart's peak draw is ~1.8A during the 1-2 second solenoid firing, and under 600mA the rest of the time. A 3A adapter provides comfortable headroom. Do NOT use a 5V/1A adapter — the solenoid pulse will cause a brownout.

---

## 5. WebSocket Protocol & Firmware Architecture

### 5.1 Firmware State Machine

```
                    ┌──────────┐
          ┌────────►│  DEEP    │ (overnight, 10µA)
          │         │  SLEEP   │
          │         └────┬─────┘
          │              │ RTC alarm (7am)
          │              ▼
          │         ┌──────────┐
          │    ┌───►│  LIGHT   │ (daytime idle, 5mA)
          │    │    │  SLEEP   │ WiFi maintained
          │    │    └────┬─────┘
          │    │         │ PIR trigger
          │    │         ▼
  9pm     │    │    ┌──────────┐
  timeout │    │    │  AWAKE   │ Open/reconnect WebSocket
          │    │    │  IDLE    │ NeoPixel welcome animation
          │    │    └────┬─────┘
          │    │         │ WS message: "user_authenticated"
          │    │         ▼
          │    │    ┌──────────┐
          │    │    │  ACTIVE  │ Door unlocked, camera on
          │    │    │  SESSION │ Audio streaming bidirectional
          │    │    └────┬─────┘
          │    │         │ Door closed + timeout
          │    │         │
          │    └─────────┘
          │
          └── (triggered by RTC alarm at 9pm)
```

### 5.2 WebSocket Message Format

All messages are JSON over a single WebSocket connection to the Vercel backend.

**ESP32 → Cloud:**

Audio chunk (sent every 20-40ms during active session):
```json
{
  "type": "audio_chunk",
  "data": "base64-encoded-PCM-16kHz-16bit-mono...",
  "timestamp": 1710000000000
}
```

Camera snapshot:
```json
{
  "type": "camera_snapshot",
  "data": "base64-encoded-JPEG...",
  "trigger": "door_opened",
  "timestamp": 1710000000000
}
```
Valid `trigger` values: `"door_opened"`, `"item_placed"`, `"item_removed"`, `"manual"`

Sensor events:
```json
{
  "type": "event",
  "event": "pir_triggered",
  "timestamp": 1710000000000
}
```
Valid `event` values: `"pir_triggered"`, `"door_opened"`, `"door_closed"`, `"session_timeout"`

Status heartbeat (every 30 seconds):
```json
{
  "type": "heartbeat",
  "battery_pct": 85,
  "wifi_rssi": -45,
  "uptime_seconds": 3600,
  "free_heap": 120000
}
```
`battery_pct` is `null` if wall-powered.

**Cloud → ESP32:**

Audio response (streamed in chunks as ElevenLabs generates them):
```json
{
  "type": "audio_chunk",
  "data": "base64-encoded-PCM...",
  "sequence": 42,
  "final": false
}
```

Unlock door command:
```json
{
  "type": "command",
  "action": "unlock_door",
  "duration_ms": 1500
}
```

Set LED pattern command:
```json
{
  "type": "command",
  "action": "set_leds",
  "pattern": "welcome",
  "positions": [3, 4, 5]
}
```
Valid `pattern` values: `"welcome"`, `"listening"`, `"item_position"`, `"error"`, `"idle"`. `positions` is optional (specific LED indices to highlight).

Take photo command:
```json
{
  "type": "command",
  "action": "take_photo"
}
```

User context (after NFC auth):
```json
{
  "type": "user_authenticated",
  "user_id": "alice_123",
  "display_name": "Alice",
  "nickname": "Bookworm"
}
```

### 5.3 Audio Pipeline Detail

```
CAPTURE (mic → cloud):
  ICS-43434 → I2S0 → DMA buffer (512 samples) → WiFi TX → WebSocket

  Sample rate: 16000 Hz
  Bit depth: 16-bit (downsampled from 24-bit I2S)
  Channels: mono
  Buffer size: 512 samples = 32ms per chunk
  Encoding: raw PCM (base64 in JSON) — or Opus if bandwidth is tight
  Latency contribution: ~32ms (one buffer fill)

PLAYBACK (cloud → speaker):
  WebSocket → WiFi RX → ring buffer (4096 samples) → I2S1 → MAX98357A → Speaker

  Sample rate: 16000 Hz (or 22050 Hz depending on ElevenLabs output)
  Ring buffer: 4096 samples = ~256ms of audio
  Purpose of ring buffer: smooth over WiFi jitter
  Latency contribution: ~128ms (half-buffer pre-fill before playback starts)
```

**Total audio round-trip latency estimate:**
- Mic capture buffer: ~32ms
- WiFi upload: ~20-50ms
- Cloud processing (Anthropic + ElevenLabs): ~300-1500ms (dominant factor)
- WiFi download: ~20-50ms
- Playback buffer pre-fill: ~128ms
- **Total: ~500-1800ms** (mostly cloud processing time)

### 5.4 Firmware Pseudocode (Arduino/ESP-IDF)

```cpp
// Main loop structure (simplified)

void setup() {
  init_wifi();
  init_i2s_mic(GPIO1, GPIO2, GPIO3);    // I2S port 0
  init_i2s_speaker(GPIO38, GPIO39, GPIO40); // I2S port 1
  init_camera(OV2640_PINS);
  init_neopixels(GPIO41, NUM_LEDS);
  init_solenoid(GPIO42);
  init_pir(GPIO14);       // RTC-capable GPIO — required for deep sleep ext0 wake
  init_white_leds(GPIO47);

  // Wake sources — two different mechanisms for two sleep modes:
  //
  // DEEP SLEEP wake (overnight): use ext0 on an RTC GPIO (0–21 on ESP32-S3).
  //   GPIO14 is RTC-capable, so ext0 works here.
  esp_sleep_enable_ext0_wakeup(GPIO_NUM_14, HIGH); // PIR triggers deep sleep wake
  esp_sleep_enable_timer_wakeup(SLEEP_DURATION);   // RTC alarm for morning wake

  // LIGHT SLEEP wake (daytime idle): use gpio_wakeup on any GPIO.
  //   ext0 also works for light sleep on RTC GPIOs, but gpio_wakeup_enable()
  //   is more flexible and the recommended API for light sleep.
  gpio_wakeup_enable(GPIO_NUM_14, GPIO_INTR_HIGH_LEVEL);
  esp_sleep_enable_gpio_wakeup();
}

void loop() {
  switch (state) {
    case LIGHT_SLEEP:
      esp_light_sleep_start();
      if (wakeup_cause == PIR) {
        state = AWAKE_IDLE;
      }
      break;

    case AWAKE_IDLE:
      ws_connect("wss://your-app.vercel.app/ws/stewart");
      neopixels_animate(WELCOME);
      ws_send(event("pir_triggered"));
      state = WAITING_FOR_AUTH;
      break;

    case WAITING_FOR_AUTH:
      // Listen for user_authenticated message
      if (ws_received("user_authenticated")) {
        fire_solenoid(1500); // unlock for 1.5 sec
        white_leds(ON);
        take_and_send_photo("door_opened");
        start_audio_streaming();
        state = ACTIVE_SESSION;
      }
      if (timeout(30_SECONDS)) {
        state = LIGHT_SLEEP;
      }
      break;

    case ACTIVE_SESSION:
      // Audio streaming runs on separate FreeRTOS tasks
      // Camera snapshots triggered by cloud commands
      // NeoPixel patterns triggered by cloud commands
      process_ws_messages();
      if (door_closed && timeout(10_SECONDS)) {
        stop_audio_streaming();
        white_leds(OFF);
        neopixels_animate(IDLE);
        state = LIGHT_SLEEP;
      }
      break;
  }
}
```

---

## 6. Cloud Integration Notes

### 6.1 Stack Overview

```
Phone (React TSX)  ←──── NFC auth, screen UI, fallback audio
        │
        ▼
Vercel (serverless + edge)  ←──── WebSocket relay, API routes
        │
    ┌───┴───┐
    ▼       ▼
Supabase   Anthropic Claude
(Postgres)  (Vision + Conversation)
    │            │
    │            ▼
    │       ElevenLabs
    │       (Voice synthesis)
    │
    ├── Users table (NFC ID, name, nickname, history)
    ├── Items table (item_id, name, photos, condition, current_holder)
    ├── Transactions table (who, what, when, direction in/out)
    └── Reviews table (user_id, item_id, review_text, rating)
```

### 6.2 Vercel WebSocket Relay

The Vercel backend acts as a relay between the ESP32 and the AI services. It:

1. **Receives audio** from ESP32 → forwards to ElevenLabs (or Anthropic for transcription)
2. **Receives text response** from Anthropic → forwards to ElevenLabs for speech synthesis
3. **Streams audio response** from ElevenLabs → forwards to ESP32
4. **Receives camera photos** from ESP32 → sends to Anthropic vision API for item identification
5. **Manages state** — tracks which user is authenticated, what items are in the box, conversation context

**Important for software team:** The ESP32 should be treated as a dumb I/O device. It streams audio and photos up, plays audio and executes commands down. All intelligence lives in the cloud. This keeps the firmware simple and the iteration cycle fast — you change behavior by updating the Vercel backend, not by reflashing hardware.

### 6.3 ElevenLabs Integration

- Use the **WebSocket streaming API**, not REST. Streaming lets you start playing audio before the full response is generated.
- Output format: PCM 16-bit at 16kHz or 22050 Hz (match what the ESP32 I2S is configured for)
- The personality engine (the "bubbly community grandmother" from the PRD) lives in the system prompt sent to Anthropic. ElevenLabs just voices whatever text Anthropic produces.
- Voice selection: Pick a warm, friendly voice from the ElevenLabs library. Test a few with your team.

### 6.4 Anthropic Vision API for Item Identification

When the camera sends a snapshot, the backend sends it to Claude with a prompt like:

```
You are an inventory system for a community sharing station. 
Identify the item in this image. Return JSON:
{
  "item_type": "book" | "board_game" | "other" | "empty",
  "title": "...",
  "author": "..." (if book),
  "condition": "good" | "fair" | "poor",
  "notes": "..."
}
```

This is where the OV5640 upgrade pays off — a sharper image means more reliable identification.

---

## 7. Simulation & Testing

### 7.1 Wokwi Simulation (Browser-Based)

[Wokwi](https://wokwi.com) is a free online simulator that supports ESP32-S3 and many of our peripherals. It won't simulate the full audio pipeline or WebSocket connection, but it CAN validate:

- GPIO pin assignments don't conflict
- NeoPixel animations work correctly
- Solenoid firing logic (timing, safety timeout)
- PIR wake behavior
- State machine transitions
- LED patterns

**Setting up a Wokwi project:**

1. Go to [wokwi.com/projects/new/esp32-s3](https://wokwi.com/projects/new/esp32-s3)
2. Add components in `diagram.json`:

```json
{
  "version": 1,
  "author": "Team Minions",
  "editor": "wokwi",
  "parts": [
    { "type": "board-esp32-s3-devkitc-1", "id": "esp", "top": 0, "left": 0 },
    { "type": "wokwi-neopixel-strip", "id": "strip1", "top": 150, "left": 0,
      "attrs": { "pixels": "10" } },
    { "type": "wokwi-pir-motion-sensor", "id": "pir1", "top": -100, "left": 0 },
    { "type": "wokwi-led", "id": "led1", "top": 150, "left": 200,
      "attrs": { "color": "white" } },
    { "type": "wokwi-led", "id": "solenoid_indicator", "top": 150, "left": 250,
      "attrs": { "color": "red", "label": "SOLENOID (simulated)" } }
  ],
  "connections": [
    ["esp:GPIO41", "strip1:DIN", "green", []],
    ["esp:5V", "strip1:VCC", "red", []],
    ["esp:GND.1", "strip1:GND", "black", []],
    ["esp:GPIO46", "pir1:OUT", "orange", []],
    ["esp:5V", "pir1:VCC", "red", []],
    ["esp:GND.2", "pir1:GND", "black", []],
    ["esp:GPIO47", "led1:A", "yellow", []],
    ["led1:C", "esp:GND.3", "black", []],
    ["esp:GPIO42", "solenoid_indicator:A", "red", []],
    ["solenoid_indicator:C", "esp:GND.4", "black", []]
  ]
}
```

3. Write test firmware that exercises the state machine without needing WiFi/audio.

### 7.2 Unit Testing Strategy

| Subsystem | Test Method | What to Verify |
|-----------|------------|----------------|
| NeoPixels | Wokwi simulation | Patterns, colors, positions, brightness |
| PIR wake | Wokwi simulation | Wake from sleep, debounce, timeout |
| Solenoid timing | Wokwi (LED as proxy) | Never >20s, correct pulse width |
| I2S mic input | Bench test with scope/serial | Audio captured, correct sample rate |
| I2S speaker output | Bench test (play sine wave) | Clean audio, no crackling |
| Camera JPEG | Bench test (save to SD) | Correct resolution, good exposure |
| WiFi + WebSocket | Bench test vs local server | Connect, send/receive JSON, reconnect |
| Full integration | Bench test vs Vercel staging | End-to-end voice + vision flow |

### 7.3 Bench Testing Without Cloud

For hardware testing before the cloud backend is ready, create a simple local WebSocket server:

```python
# test_server.py — run on your laptop
# Requires: pip install websockets
import asyncio
import websockets
import json

async def handler(websocket):
    print("Stewart connected!")
    # Send a fake auth message after 5 seconds
    await asyncio.sleep(5)
    await websocket.send(json.dumps({
        "type": "user_authenticated",
        "user_id": "test_user",
        "display_name": "Test Person",
        "nickname": "Tester"
    }))
    # Listen and print everything Stewart sends
    async for message in websocket:
        data = json.loads(message)
        if data["type"] == "audio_chunk":
            print(f"Audio chunk: {len(data['data'])} bytes")
        elif data["type"] == "camera_snapshot":
            print(f"Photo received: {len(data['data'])} bytes")
            import base64
            with open("last_photo.jpg", "wb") as f:
                f.write(base64.b64decode(data["data"]))
        else:
            print(f"Event: {data}")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Test server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever

asyncio.run(main())
```

Point the ESP32's WebSocket URL to `ws://YOUR_LAPTOP_IP:8765` during development.

---

## 8. Physical Enclosure & Assembly

### 8.1 Target Dimensions

- **Exterior:** ~14" × 14" × 14" (fits books and board games)
- **Interior usable space:** ~12" × 12" × 12"
- **Door:** Front-facing, spring-hinged, opens outward and upward
- **Material:** Plywood (MVP), potentially laser-cut acrylic later

### 8.2 Component Mounting Locations

```
        TOP VIEW (lid removed)
    ┌─────────────────────────┐
    │                         │
    │   ┌─────────────────┐   │
    │   │ ITEM AREA       │   │  ← White LEDs point here
    │   │                 │   │  ← Camera looks down at this
    │   │                 │   │
    │   └─────────────────┘   │
    │                         │
    │ [NeoPixel strip along   │  ← Along bottom edge or shelf dividers
    │  inner walls]           │
    │                         │
    └─────────────────────────┘

        FRONT VIEW
    ┌─────────────────────────┐
    │ [Camera]     [White LED]│  ← Top inside, looking down
    │                         │
    │     (item area)         │
    │                         │
    │ [Speaker]    [Mic]      │  ← Lower front, facing outward
    ├═════════════════════════┤  ← Door hinge line
    │ ████ DOOR ██████████████│
    │ [PIR sensor]            │  ← Outside, faces the approaching person
    │        [NeoPixel status]│  ← Outside, visible indicator
    └─────────────────────────┘

        SIDE/BACK VIEW
    ┌─────────────────────────┐
    │                         │
    │ [ESP32 + breadboard     │  ← Mounted on back wall or base
    │  mounted here]          │
    │                         │
    │ [Boost converter]       │  ← Near solenoid
    │ [Solenoid] ─── [Door]   │  ← Solenoid mounted on frame, latch catches door
    │                         │
    │ [USB-C power entry] ○   │  ← Bottom or back, with strain relief
    └─────────────────────────┘
```

### 8.3 Assembly Order

1. **Build the box** — cut panels, glue/screw together, leave front open for door
2. **Install door** with spring hinges — verify it swings open freely
3. **Mount solenoid** on door frame — test latch alignment with door closed
4. **Mount ESP32 + breadboard** on back wall with standoffs
5. **Wire power** — USB-C entry → breadboard power rails → boost converter
6. **Wire solenoid circuit** — boost converter → capacitor → MOSFET → solenoid (test with multimeter before powering on!)
7. **Mount and wire camera** — top inside, angled down at item area
8. **Mount and wire mic** — lower front, small hole in enclosure for sound
9. **Mount and wire speaker** — sealed chamber in lower front
10. **Install NeoPixel strip** — along inner walls or shelf edges
11. **Install white LEDs** — top inside, pointing down
12. **Mount PIR sensor** — outside, lower front, small hole for lens
13. **Flash firmware and test**

### 8.4 Weatherproofing (Outdoor Deployments)

- **Wood:** Marine polyurethane (3 coats minimum)
- **Electronics:** Conformal coating spray on all boards
- **Door seal:** Rubber gasket / weather stripping around door edges
- **Camera/mic:** Small acrylic window for camera, mesh cover for mic
- **Cable entry:** Grommet or cable gland where USB-C enters

---

## 9. BOM & Procurement Tracker

See the separate `stewart_shopping_list_v3.xlsx` spreadsheet for the full BOM with prices, quantities, Micro Center and Amazon links.

**Quick summary per unit:**
- Wall-powered: ~$100-110
- With solar: ~$130-140
- 4 units (wall-powered): ~$400-440

**Procurement status:** *(update this as you buy things)*

| Item | Status | Ordered from | ETA |
|------|--------|-------------|-----|
| ESP32-S3 CAM | ☐ Not ordered | | |
| OV5640 camera | ☐ Not ordered | | |
| ICS-43434 mic | ☐ Not ordered | | |
| INMP441 mic (backup) | ☐ Not ordered | | |
| MAX98357A amp | ☐ Not ordered | | |
| Speaker 3" 4Ω | ☐ Not ordered | | |
| Solenoid lock | ☐ Not ordered | | |
| IRLZ44N MOSFET | ☐ Not ordered | | |
| 1N4007 diodes | ☐ Not ordered | | |
| WS2812B strip | ☐ Not ordered | | |
| White LEDs | ☐ Not ordered | | |
| PIR sensor | ☐ Not ordered | | |
| USB-C adapter | ☐ Not ordered | | |
| MT3608 boost converter | ☐ Not ordered | | |
| 1000µF capacitor | ☐ Not ordered | | |
| Breadboard | ☐ Not ordered | | |
| Jumper wires | ☐ Not ordered | | |
| JST connectors | ☐ Not ordered | | |
| Resistors (10KΩ) | ☐ Not ordered | | |
| Resistors (330Ω) | ☐ Not ordered | | |

---

## 10. Known Issues & Gotchas

### Hardware

- **GPIO46 is a boot strap pin on ESP32-S3.** Do NOT use it for general I/O. Driving it during boot can prevent the chip from starting. We use GPIO14 (RTC-capable) for the PIR sensor instead.
- **ESP32-S3 GPIO conflicts:** Some GPIOs (26-32) may be used internally for PSRAM on WROOM modules. Always verify with your specific board's schematic before assigning pins.
- **White LEDs must use a transistor switch.** ESP32-S3 GPIOs are rated for max 40mA. Multiple LEDs in parallel will exceed this. Always switch LED power from the 5V rail through an NPN transistor (2N2222) or N-channel MOSFET.
- **Camera + WiFi + I2S simultaneously:** This pushes the ESP32-S3's DMA bandwidth. If you see audio glitches during camera capture, take photos between audio chunks, not during.
- **MT3608 noise:** Boost converters generate switching noise. Keep the 12V wiring away from the I2S audio lines. If you hear a whine in the speaker, add a 100µF capacitor on the 5V rail near the MAX98357A.
- **PIR false triggers:** The HC-SR501 can false-trigger from rapid temperature changes (sunlight, HVAC vents). Debounce in firmware (require 2 triggers within 3 seconds). Adjust sensitivity pot if needed.
- **OV5640 purple tint:** Some OV5640 modules produce a purple tint at default settings. Lower the XCLK frequency to 10 MHz if this happens. This is a known issue in the community.

### Software

- **WebSocket reconnection:** WiFi WILL drop occasionally. Firmware must handle reconnection gracefully — buffer audio locally and resume streaming when connection returns.
- **ElevenLabs latency:** First response is always slower (~1-2s) due to model cold start. Subsequent responses in the same session are faster (~300-500ms). Keep the WebSocket to ElevenLabs alive during the session.
- **Base64 overhead:** Base64 encoding adds ~33% to payload size. For audio streaming, consider sending raw binary WebSocket frames instead of JSON with base64. This is an optimization for later.

### Physical

- **Solenoid heat:** Even brief operation heats the coil. If testing repeatedly, let it cool between firings.
- **Spring hinge tension:** Too weak = door doesn't pop open. Too strong = door slams and scares people. Test with actual items in the box (weight changes the dynamics).
- **Speaker chamber seal:** Any air leak in the speaker's sealed chamber kills the bass response. Use hot glue or silicone to seal joints.

---

## 11. Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-10 | Max | Initial document created. Full component reference, wiring, power budget, WebSocket protocol, simulation setup, enclosure guide. |
| 2026-03-10 | Max | **Fixes from review:** (1) Moved PIR from GPIO46 (boot strap, non-RTC) to GPIO14 (RTC-capable). (2) Fixed sleep API: use gpio_wakeup_enable() + esp_sleep_enable_gpio_wakeup() for light sleep, ext0 for deep sleep. (3) Fixed solenoid power math: 500mA@12V = ~1.4A from 5V input via boost converter; peak system draw is ~1.8A not <1A. (4) Made transistor-switched white LEDs the default (GPIO can't drive 3 LEDs directly). (5) Corrected ESP32 I2S claim (base ESP32 has 2 I2S peripherals, not 1). (6) Fixed SD card capacity (SDHC/SDXC supported, not limited to 4GB). (7) Split JSON examples into individually valid blocks (removed comments and union syntax). (8) Fixed websockets test server to use modern async with serve() pattern. (9) Added GPIO46 boot strap warning. |
| | | |

---

*This document lives alongside the codebase. If you change hardware, update this doc in the same commit.*
