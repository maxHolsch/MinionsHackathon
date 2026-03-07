# Sharing Station — Technical Documentation

A voice-powered community sharing station where neighbors lend and borrow books, board games, and other items. An AI personality (via ElevenLabs) manages conversations, while a FastAPI backend handles inventory, user identity, and hardware control.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    ElevenLabs Cloud                       │
│              (Voice AI Agent + LLM + TTS)                │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Browser WebRTC Audio (mic + speaker on phone / Pi)  │ │
│  │ Speech-to-Text → LLM → Text-to-Speech               │ │
│  └──────────────────────────────┬───────────────────────┘ │
└─────────────────────────────────┼────────────────────────┘
                                  │ Tool calls (client tools via browser)
                                  ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Server (your machine)            │
│                                                          │
│  /api/tools/camera      → services/hardware → camera     │
│  /api/tools/log-item    → services/inventory             │
│  /api/tools/inventory   → services/inventory             │
│  /api/tools/user-info   → services/users                 │
│  /api/tools/lights      → services/hardware → LEDs       │
│  /api/tools/lock        → services/hardware → servo      │
│  /api/auth/nfc          → services/users                 │
│                                                          │
│  /conversation/token    → ElevenLabs conversation token  │
│  /conversation/state    → web session status             │
│  /conversation/stop     → stop/reset session state       │
│  /health                → status check                   │
│  /                      → static/index.html (phone UI)   │
└──────────────────────────────────────────────────────────┘
```

### How a conversation flows

1. **User taps NFC tag** on phone → phone calls `POST /api/auth/nfc` with the tag ID
2. Server maps NFC ID to a known user and returns their profile
3. Phone/web dashboard requests `POST /conversation/token`
4. Browser starts ElevenLabs session via **WebRTC** and sends user context
5. **User speaks** → ElevenLabs transcribes → LLM decides what to do
6. If the LLM needs to take an action, it fires a **client tool call** handled in the browser, which then calls your server API
7. Your server executes the action (take photo, log item, etc.) and returns a result
8. The LLM uses the result to continue the conversation
9. When done, the session ends and `POST /conversation/stop` is called

---

## File-by-File Breakdown

### `main.py` — Application Entry Point

The FastAPI application that ties everything together.

- **Lifespan handler**: Prints startup/shutdown messages and ensures the conversation is cleaned up on exit.
- **Router mounting**: Includes the tool endpoints at `/api/tools/` and auth at `/api/auth/`.
- **Conversation endpoints**: `POST /conversation/token`, `POST /conversation/state`, `POST /conversation/mic`, `POST /conversation/stop`.
- **Static files**: Mounted last at `/` so it serves `static/index.html` for the phone UI without intercepting API routes.
- **Health check**: `GET /health` returns server status and whether a conversation is active.

Run with: `python main.py` (starts uvicorn on port 8000).

---

### `config.py` — Environment Variables

`config.py` loads the core AI keys from `.env`. Supabase variables are read by `database/client.py`.

| Variable | Purpose |
|----------|---------|
| `ELEVENLABS_API_KEY` | Authenticates with ElevenLabs API |
| `ELEVENLABS_AGENT_ID` | Identifies which ElevenLabs agent to use |
| `ANTHROPIC_API_KEY` | Used by the Pi camera for vision-based item identification |
| `VOICE_RUNTIME` | `webrtc` (default) or `python` fallback for server-side audio |
| `SUPABASE_URL` | Supabase project URL used by `database/client.py` |
| `SUPABASE_KEY` | Supabase anon/service key used by `database/client.py` |

`SUPABASE_URL`/`SUPABASE_KEY` are required for auth/user/inventory flows (`/api/auth/nfc`, `/api/tools/user-info`, `/api/tools/log-item`, `/api/tools/inventory`).

---

### `conversation.py` — ElevenLabs Session Manager

The `ConversationManager` class wraps the ElevenLabs Conversational AI SDK.

**Key concepts:**
- **`start(user_name)`**: Creates a new `Conversation` object with dynamic variables (so the agent knows who it's talking to), a `DefaultAudioInterface` (uses PyAudio to capture mic input and play speaker output), and callback functions that log what the agent and user say.
- **`stop()`**: Ends the session and waits for cleanup.
- **`wait()`**: Blocks until the session ends (used by the CLI runner).

This module is the legacy/server-audio path (`VOICE_RUNTIME=python`). In the default WebRTC flow, browser clients own mic/speaker and this file is not used by request routes.

---

### `run_conversation.py` — CLI Voice Session

A standalone script to start a voice conversation from the terminal without running the full web server.

```bash
python run_conversation.py              # Defaults to "Peter"
python run_conversation.py --user Alice # Start as Alice
```

Useful for quick testing. Press `Ctrl+C` to stop.

---

### `deploy/install_pi_services.sh` — Boot Automation Installer

Installs two `systemd` services on Raspberry Pi:
- `sharing-station-backend.service`: starts FastAPI with `VOICE_RUNTIME=webrtc`
- `sharing-station-kiosk.service`: starts Chromium in kiosk mode on `http://localhost:8000/`

It auto-detects your project path and writes service files to `/etc/systemd/system/`.

### `deploy/start_chromium_kiosk.sh` — Kiosk Launcher

Minimal Chromium launcher used by the kiosk service. It enables full-screen mode and auto media permission UI suppression for unattended station use.

---

### `routes/tools.py` — Tool Webhook Endpoints

These are the 7 endpoints that ElevenLabs calls when the AI agent decides to use a tool. Each endpoint has a Pydantic request model that must match the parameter names configured in the ElevenLabs dashboard exactly.

#### `POST /api/tools/camera`
- **Called when**: Agent needs to see what's in the box (deposit verification, pickup confirmation)
- **Input**: `reason` (string) — why the photo is being taken
- **Action**: Calls `camera.capture_and_identify(reason)` from the hardware layer
- **Returns**: `{ items_detected: [...], raw_description: "..." }`

#### `POST /api/tools/log-item`
- **Called when**: Agent has confirmed an item deposit or retrieval with the user
- **Input**: `item_name`, `action` ("deposit"/"retrieval"), `user_id`, optional `condition`, `review`, `slot_row` (0-2), `slot_col` (0-9)
- **Action**: Adds or removes the item from inventory. For deposits, `slot_row`/`slot_col` assign the item to a physical slot in the 3×10 grid.
- **Returns**: `{ success: true, inventory_count: N }`
- **Error**: Returns `503` if Supabase credentials are not configured

#### `GET /api/tools/available-slots`
- **Called when**: Agent needs to find an empty slot before depositing an item
- **Input**: None
- **Returns**: `{ available_slots: [[row, col], ...], total_available: N }` — list of unoccupied positions in the 3×10 grid
- **Error**: Returns `503` if Supabase credentials are not configured

#### `GET /api/tools/inventory`
- **Called when**: User asks what's available, or agent needs context for a pickup
- **Input**: None
- **Returns**: `{ items: [...] }` — full list of current items with metadata
- **Error**: Returns `503` if Supabase credentials are not configured

#### `POST /api/tools/user-info`
- **Called when**: Agent learns something about the user (gives them a nickname, learns a preference)
- **Input**: `user_id`, optional `nickname`, `memory`, `preferences`
- **Action**: Updates the user's profile in the user store
- **Returns**: `{ success: true }`

#### `POST /api/tools/lights`
- **Called when**: Agent wants to highlight an item location, play a welcome animation, etc.
- **Input**: `mode` ("highlight_item"/"welcome"/"goodbye"/"idle"/"error"), optional `position` (1-6), `color` (hex)
- **Action**: Calls `leds.set_mode(...)` from the hardware layer
- **Returns**: `{ success: true, mode: "..." }`

#### `POST /api/tools/lock`
- **Called when**: Agent unlocks the door after authentication, or locks it when done
- **Input**: `action` ("unlock"/"lock")
- **Action**: Calls `servo.set_lock(action)` from the hardware layer
- **Returns**: `{ success: true, state: "unlocked"/"locked" }`

---

### `routes/auth.py` — NFC Authentication

`POST /api/auth/nfc` maps an NFC tag ID to a known user.

Current behavior:
- Looks up the user in Supabase via `users.nfc_uuid` (fallback: `users.nfc_id` for older schemas).
- If no user exists, creates a new user record for that NFC tag.
- Marks the scanned user as active (`is_active=true`) when that column exists.
- Starts the conversation immediately using the resolved user profile.
- Returns `503` if Supabase credentials are not configured.

Seeded sample users in `database/schema.sql` and migrations:
- `abc123` → Peter (`nickname`: Tiger)
- `def456` → Alice
- `ghi789` → Bob

---

### `services/inventory.py` — Inventory Store

Inventory service is Supabase-only and uses collaborator schema in `database/schema.sql`.

**Methods:**
- `add(name, user_id, condition, review)` — inserts an `items` row (`status='available'`) and logs a `transactions` row.
- `remove(name, user_id)` — marks the first matching available item as `borrowed` (or deletes in legacy schemas) and logs a transaction.
- `list_all()` — returns available items normalized to the API shape used by the dashboard/tool routes.
- Inventory endpoints return `503` when Supabase credentials are missing.

The API shape remains stable: `id`, `name`, `type`, `deposited_by`, `deposited_at`, `condition`, `review`, `position`.
When the DB schema has no explicit slot columns, `position` is synthesized from list order for the 3×10 grid UI.

---

### `services/users.py` — User Store

User service is Supabase-only and reads/writes from `users` + `memories` tables.

**Methods:**
- `get_or_create_by_nfc(nfc_id)` — resolves NFC tags, creating users when needed.
- `get(user_id)` / `get_by_nfc(nfc_id)` — fetches normalized user profiles.
- `update(user_id, nickname, memory, preferences)` — updates nickname and stores memory/preferences entries in the `memories` table.
- User endpoints return `503` when Supabase credentials are missing.

Normalized user shape returned to routes: `id`, `nfc_id`, `name`, `nickname`, `memories`, `preferences`, `is_active`.

---

### `services/hardware.py` — Hardware Abstraction

Auto-detects whether the code is running on a Raspberry Pi (checks for `/sys/firmware/devicetree/base/model`).

- **On desktop**: imports `MockCamera`, `MockLEDs`, `MockServo` — these just print to console
- **On Pi**: imports `PiCamera`, `PiLEDs`, `PiServo` — these control real hardware

Exports three singleton instances: `camera`, `leds`, `servo`. The rest of the app imports these and doesn't need to know which implementation is running.

---

### `hardware/mock_camera.py`

Returns a hardcoded detection result (Dune by Frank Herbert) for every "photo." Prints the reason to console. Used for desktop testing so you don't need a real camera.

### `hardware/mock_leds.py`

Prints LED mode, position, and color to console. No real hardware interaction.

### `hardware/mock_servo.py`

Prints lock action to console. Returns simulated state.

### `hardware/pi_camera.py`

The real camera implementation for Raspberry Pi:

1. Uses `picamera2` to capture a JPEG photo to `/tmp/station_photo.jpg`
2. Base64-encodes the image
3. Sends it to **Anthropic Claude Sonnet** with a vision prompt asking it to identify items
4. Parses the JSON response into `{ items_detected: [...], raw_description: "..." }`

This is how the sharing station "sees" — the ElevenLabs agent calls the camera tool, the Pi takes a photo, Anthropic's vision model identifies the items, and the result goes back to the ElevenLabs agent to continue the conversation.

### `hardware/pi_leds.py` / `hardware/pi_servo.py`

Skeleton implementations for real GPIO-controlled NeoPixel LEDs and servo motor (for the door lock). These have TODO markers and need to be filled in with your specific hardware wiring.

---

### `static/index.html` — Dev Dashboard

A three-column dark-themed dashboard served at the root URL for dry-run testing without any physical hardware. Polls `GET /api/status` every second.

**Left panel — Controls:**
- NFC tap buttons for Peter, Alice, Bob, and a new neighbor (simulated)
- Lock toggle (unlock / lock)
- Camera snap with configurable reason text
- Lights controller (mode, row, col, color)
- Log item form (name, user ID, deposit or retrieval)

**Center panel — Activity log:**
- Real-time event stream merged from local interactions and server `station["events"]`
- Color-coded by category: LOCK (amber), CAMERA (blue), LIGHTS (purple), LOG (green), AUTH (orange), CONV (green), ERROR (red)

**Right panel — Hardware state:**
- Lock icon (🔒/🔓) with current state
- 3×10 LED grid — dots glow amber when active, dim amber when a slot holds an item
- Last camera result (detected items)
- Inventory list with `[row, col]` positions

In production, the NFC tap comes from the phone's actual NFC reader calling the same `/api/auth/nfc` endpoint — the rest of the flow is identical.

---

### `station_state.py` — Shared Mock Hardware State

An in-memory dict written to by mock hardware classes and read by `GET /api/status`.

```python
station = {
    "lock": "locked",
    "led": {"mode": "idle", "position": None, "color": None},
    "camera": None,
    "events": [],   # last 100 events, newest first
}
```

`log_event(category, message, data=None)` appends timestamped events (kept at most 100). On a real Pi the hardware classes bypass this dict entirely.

---

### `routes/status.py` — Status Polling Endpoint

`GET /api/status` returns the full station state in one payload:

```json
{
  "conversation_active": false,
  "lock": "locked",
  "led": {"mode": "idle", "position": null, "color": null},
  "camera": null,
  "events": [...],
  "inventory": [...],
  "inventory_error": null
}
```

Imports the `inventory` singleton directly from `routes/tools`.

---

## Running the Project

### Prerequisites
- Python 3.10+
- Chromium browser (for WebRTC kiosk/client mode)
- ElevenLabs account with a Conversational AI agent configured
- Anthropic API key (for Pi camera vision, optional on desktop)
- PortAudio system library only if using legacy server-audio mode (`VOICE_RUNTIME=python`)

### Setup
```bash
cd sharing-station
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Running
```bash
# Terminal 1: Start the server
python main.py

# Terminal 2 (optional, legacy mode only): Start a server-audio conversation directly
# Requires VOICE_RUNTIME=python and PyAudio/PortAudio
python run_conversation.py --user Peter
```

### Dry-Run Dashboard

Once the server is running, open **http://localhost:8000** in your browser. You'll see the dev dashboard — no NFC reader, camera, LEDs, or microphone required.

Walk through the full flow:
1. Click **Peter** under "NFC Tap" — authenticates Peter, **unlocks the door immediately**, and starts a browser WebRTC conversation
2. Watch the lock icon flip to 🔓 and the conversation dot turn green
3. The agent should start speaking through your speakers within a second or two
4. Click **Snap Photo** to simulate the camera identifying an item
5. Click **Log Item** (deposit) to add it to inventory — it appears in the LED grid and inventory list
6. Click **Lock** (or the agent calls it when done) — locks the door and ends the session
7. Watch the lock icon flip back to 🔒 and the conversation dot go grey

The Activity Log in the center column streams every server event in real time (hardware calls, NFC auth, inventory changes). The right column shows live hardware state.

---

### Testing endpoints without voice
```bash
# Health check
curl http://localhost:8000/health

# Check inventory
curl http://localhost:8000/api/tools/inventory

# Simulate NFC tap
curl -X POST http://localhost:8000/api/auth/nfc \
  -H "Content-Type: application/json" \
  -d '{"nfc_id": "abc123"}'

# Simulate camera snap
curl -X POST http://localhost:8000/api/tools/camera \
  -H "Content-Type: application/json" \
  -d '{"reason": "user deposited an item"}'
```

---

## Raspberry Pi Porting Guide

This section is the full handoff for running the station on Raspberry Pi with the current **WebRTC-first** architecture.

### Target Architecture on Pi

- FastAPI backend runs as a `systemd` service
- Chromium runs in fullscreen kiosk mode on boot
- Browser owns mic/speaker via ElevenLabs WebRTC
- Python backend owns tools, Supabase, and hardware (camera/LEDs/servo)

### 1. Pi OS + Hardware Baseline

1. Use Raspberry Pi OS (Bookworm) with Desktop.
2. Connect microphone + speaker (or headset).
3. Connect camera module and validate:
   ```bash
   libcamera-hello
   ```
4. If using GPIO hardware, wire LEDs + servo and confirm power stability.

### 2. Install System Packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip chromium-browser
```

If you plan to run legacy server-audio mode (`VOICE_RUNTIME=python`), also install:

```bash
sudo apt install -y portaudio19-dev
```

### 3. Clone and Install Project

```bash
cd ~
git clone <your-repo-url> MinionsHackathon
cd MinionsHackathon/MinionsHackathon/sharing-station
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least:

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_AGENT_ID`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `VOICE_RUNTIME=webrtc`

### 4. One-Time Smoke Test Before Services

```bash
source venv/bin/activate
python main.py
```

Then from Pi browser (or another device on LAN), open:

- `http://<pi-ip>:8000`
- tap a mock NFC user in dashboard
- confirm WebRTC connects and agent speaks

### 5. Install Boot Services (Backend + Kiosk)

From `sharing-station/`:

```bash
chmod +x deploy/*.sh
./deploy/install_pi_services.sh
```

This installs and enables:

- `sharing-station-backend.service`
- `sharing-station-kiosk.service`

### 6. Verify Service Health

```bash
sudo systemctl status sharing-station-backend.service
sudo systemctl status sharing-station-kiosk.service
journalctl -u sharing-station-backend.service -n 100 --no-pager
journalctl -u sharing-station-kiosk.service -n 100 --no-pager
```

Reboot test:

```bash
sudo reboot
```

After reboot, backend should be up and Chromium should auto-open `http://localhost:8000/`.

### 7. Day-2 Operations

Restart services after pulls/config changes:

```bash
sudo systemctl restart sharing-station-backend.service
sudo systemctl restart sharing-station-kiosk.service
```

Disable kiosk temporarily (keep backend running):

```bash
sudo systemctl stop sharing-station-kiosk.service
sudo systemctl disable sharing-station-kiosk.service
```

Re-enable kiosk:

```bash
sudo systemctl enable --now sharing-station-kiosk.service
```

### 8. NFC Integration on Pi

- In production, your NFC reader process should call `POST /api/auth/nfc` on tag scan.
- The response gives user context; browser session then starts/continues WebRTC flow.
- During development, the dashboard NFC buttons are enough.

### 9. Common Pi Issues

1. No kiosk window on boot:
   - Verify desktop autologin is enabled.
   - Check `DISPLAY=:0` and `XAUTHORITY=/home/<user>/.Xauthority` in kiosk service.
2. No mic/speaker audio:
   - Verify default devices and volumes via OS sound settings.
   - Test in Chromium with any mic test page.
3. ElevenLabs token errors:
   - Check `ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID` in `.env`.
4. Want old server-audio mode:
   - Set `VOICE_RUNTIME=python`, install PortAudio, and use `run_conversation.py`.

---

## Agent Prompt (ElevenLabs Dashboard)

Configure this in your ElevenLabs agent's system prompt:

```
You are the AI personality of a community sharing station — a physical box where
neighbors lend and borrow books, board games, and other items.
Your personality: warm, bubbly community grandmother who is slightly gossipy (in a
loving way). You're obsessed with fun facts, pop culture, and knowing everyone's
business. You give people affectionate nicknames. You have a quirky obsession with
counting things ("It's been 47 hours since anyone borrowed Catan!").
You are NOT a general assistant. You only help with:
- Greeting authenticated users
- Logging items in and out of the station
- Sharing what's available
- Chatting briefly about items and community context
- Controlling the physical station (camera, lights, lock)
CONVERSATION FLOW:
1. The door is already unlocked when you start speaking — the server opens it automatically
   on NFC tap. You receive the user's name, history, and `is_new_user` via dynamic variables.
   If `is_new_user` is "true", welcome them as a brand-new neighbor — introduce yourself,
   ask their name, and offer to remember them next time.
2. Ask what they're doing (dropping off or picking up)
3. DEPOSIT FLOW:
   a. Call `snap_camera_photo` to identify the item, confirm with the user
   b. Call `get_available_slots` to find an empty slot in the 3×10 grid
   c. Pick a slot — prefer filling left-to-right, top-to-bottom
   d. Call `control_lights("highlight_item", position=[row, col])` to light up the chosen slot
   e. Tell the user: "Place it in the lit-up spot!"
   f. Call `log_item` with the item details AND `slot_row` and `slot_col` for the chosen position
   g. Ask for a mini review
4. PICKUP FLOW:
   a. Call `get_inventory` to see what's available (each item has a position)
   b. Let the user choose, then call `control_lights("highlight_item", position=[row, col])`
      to show them where it is
   c. Call `snap_camera_photo` to confirm removal
   d. Call `log_item` with action="retrieval" — this frees the slot automatically
5. Brief friendly chat, then wrap up
6. When done, call `control_lock("lock")` to close the door — this automatically ends the session.
TOOL USAGE:
- Call `snap_camera_photo` when you need to see what's in the box or identify an item
- Call `get_available_slots` before depositing to find an open slot in the 3×10 grid
- Call `log_item` after confirming an item deposit or retrieval with the user.
  For deposits, always include `slot_row` and `slot_col` for the assigned position.
- Call `get_inventory` when the user asks what's available or you need context
- Call `update_user_info` to save nicknames, preferences, or conversation memories
- Call `control_lights` to highlight item positions. Positions are [row, col] in a
  3-row × 10-column grid (both 0-indexed).
- Call `control_lock("lock")` when done — this closes the door AND ends the conversation.
  Do NOT call control_lock("unlock") — the door is already open when you start speaking.
Never fabricate what's in the box. Always use the camera or inventory tools.
Keep conversations SHORT — 3-4 exchanges max unless the user wants to chat.
```

---

## Swapping for Production

| Component | Current (Hackathon) | Production |
|-----------|-------------------|------------|
| Inventory | Supabase (`items` + `transactions`) | Same tables, plus stricter validation and monitoring |
| Users | Supabase (`users` + `memories`) | Same tables, plus auth/RLS hardening |
| Camera | Mock (returns "Dune") | `pi_camera.py` with Picamera2 + Anthropic vision |
| LEDs | Mock (console print) | NeoPixel via GPIO |
| Lock | Mock (console print) | Servo via GPIO |
| NFC mapping | Supabase lookup (`nfc_uuid`/`nfc_id` fallback) | Supabase lookup (`nfc_uuid`) |
| Tunnel | Optional | Optional (only if remote internet access to local station UI/API is needed) |

---

## Future Steps / Roadmap

### Step 1 — Keep DB Schema in Sync

The active runtime client now lives in `database/client.py`, and services read collaborator tables under `database/`.

Recommended workflow:
1. Keep schema changes in `database/supabase/migrations/*.sql`
2. Regenerate/check `database/schema.sql` when migrations change
3. Set `SUPABASE_URL` + `SUPABASE_KEY` in `.env` and validate flows:
   - `POST /api/auth/nfc`
   - `POST /api/tools/log-item`
   - `GET /api/tools/inventory`
4. Confirm there are no Python imports from `max_supabase`:
   ```bash
   rg -n "from max_supabase|import max_supabase" --glob "*.py" .
   ```
5. Delete `max_supabase/` after the grep returns no matches (already removed in this repo state)

---

### Step 2 — Move to Raspberry Pi

Use the full **Raspberry Pi Porting Guide** section above for setup and boot automation.

After the base Pi deploy is up, remaining hardware-specific TODOs are:

1. **Fill in `pi_leds.py`**: Initialize NeoPixel strip on GPIO pin, implement `set_mode` by mapping `[row, col]` → LED index (`row * 10 + col`) and setting color/animation
2. **Fill in `pi_servo.py`**: Wire servo to a GPIO pin, implement `set_lock` with angle positions for locked/unlocked states
3. **Set up `picamera2`**: Already implemented in `pi_camera.py` — just needs the Pi Camera module connected
4. **NFC reader runtime process**: Wire an NFC reader (e.g., PN532) to SPI/I2C and run a background process that reads tags and calls `POST /api/auth/nfc`.

---

### Step 3 — Raspberry Pi Vibe-Coding Feedback Loop

The goal: make changes on your laptop and see them running on the Pi in seconds.

**Recommended setup:**

1. **VS Code Remote SSH** — install the "Remote - SSH" extension, connect to `pi@raspberrypi.local`, and edit files directly on the Pi. No file sync needed.

2. **`uvicorn --reload`** — run the server in reload mode on the Pi. It watches for file saves and restarts automatically:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **cloudflared optional** — only needed if you want remote internet access to the local Pi dashboard/API.

4. **Phone UI as test client** — open `http://raspberrypi.local:8000` on your phone to trigger NFC taps, view inventory, and start/stop conversations without touching physical hardware.

5. **Mock hardware flag** — set `HARDWARE_MOCK=true` in `.env` on the Pi to skip real GPIO calls while iterating on conversation logic. Flip it off only when testing physical hardware.

6. **Quick deploy from laptop** (alternative to Remote SSH):
   ```bash
   rsync -avz --exclude venv --exclude __pycache__ . pi@raspberrypi.local:~/sharing-station/
   ```
   Pair with `uvicorn --reload` on the Pi and changes land in under 2 seconds.
