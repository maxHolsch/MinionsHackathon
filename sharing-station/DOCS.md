# Sharing Station — Technical Documentation

A voice-powered community sharing station where neighbors lend and borrow books, board games, and other items. An AI personality (via ElevenLabs) manages conversations, while a FastAPI backend handles inventory, user identity, and hardware control.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    ElevenLabs Cloud                       │
│              (Voice AI Agent + LLM + TTS)                │
│                                                          │
│  ┌─────────────┐    ┌──────────────────────────────────┐ │
│  │ Microphone   │───>│ Speech-to-Text → LLM → Text-to- ││
│  │ (PyAudio)    │<───│ Speech → Speaker                 ││
│  └─────────────┘    └──────────┬───────────────────────┘ │
└─────────────────────────────────┼────────────────────────┘
                                  │ Tool calls (webhooks)
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
│  /conversation/start    → conversation.py (ElevenLabs)   │
│  /conversation/stop     → conversation.py                │
│  /health                → status check                   │
│  /                      → static/index.html (phone UI)   │
└──────────────────────────────────────────────────────────┘
```

### How a conversation flows

1. **User taps NFC tag** on phone → phone calls `POST /api/auth/nfc` with the tag ID
2. Server maps NFC ID to a known user and returns their profile
3. Phone (or server) calls `POST /conversation/start?user_name=Peter`
4. ElevenLabs agent opens a WebSocket, greets the user by name via speaker
5. **User speaks** → ElevenLabs transcribes → LLM decides what to do
6. If the LLM needs to take an action, it fires a **tool call** (webhook) to your server
7. Your server executes the action (take photo, log item, etc.) and returns a result
8. The LLM uses the result to continue the conversation
9. When done, the session ends and `POST /conversation/stop` is called

---

## File-by-File Breakdown

### `main.py` — Application Entry Point

The FastAPI application that ties everything together.

- **Lifespan handler**: Prints startup/shutdown messages and ensures the conversation is cleaned up on exit.
- **Router mounting**: Includes the tool endpoints at `/api/tools/` and auth at `/api/auth/`.
- **Conversation endpoints**: `POST /conversation/start` and `POST /conversation/stop` let you start/stop voice sessions via API (useful for testing or triggering from the phone UI).
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
| `SUPABASE_URL` | Supabase project URL used by `database/client.py` |
| `SUPABASE_KEY` | Supabase anon/service key used by `database/client.py` |

`SUPABASE_URL`/`SUPABASE_KEY` are required for user/auth flows (`/api/auth/nfc`, `/api/tools/user-info`, conversation user context).
Inventory still has an in-memory fallback for local dry runs if Supabase is unavailable.

---

### `conversation.py` — ElevenLabs Session Manager

The `ConversationManager` class wraps the ElevenLabs Conversational AI SDK.

**Key concepts:**
- **`start(user_name)`**: Creates a new `Conversation` object with dynamic variables (so the agent knows who it's talking to), a `DefaultAudioInterface` (uses PyAudio to capture mic input and play speaker output), and callback functions that log what the agent and user say.
- **`stop()`**: Ends the session and waits for cleanup.
- **`wait()`**: Blocks until the session ends (used by the CLI runner).

The ElevenLabs SDK handles all the real-time audio streaming, speech-to-text, LLM inference, and text-to-speech. Your server just needs to respond to tool call webhooks.

---

### `run_conversation.py` — CLI Voice Session

A standalone script to start a voice conversation from the terminal without running the full web server.

```bash
python run_conversation.py              # Defaults to "Peter"
python run_conversation.py --user Alice # Start as Alice
```

Useful for quick testing. Press `Ctrl+C` to stop.

---

### `routes/tools.py` — Tool Webhook Endpoints

These are the 6 endpoints that ElevenLabs calls when the AI agent decides to use a tool. Each endpoint has a Pydantic request model that must match the parameter names configured in the ElevenLabs dashboard exactly.

#### `POST /api/tools/camera`
- **Called when**: Agent needs to see what's in the box (deposit verification, pickup confirmation)
- **Input**: `reason` (string) — why the photo is being taken
- **Action**: Calls `camera.capture_and_identify(reason)` from the hardware layer
- **Returns**: `{ items_detected: [...], raw_description: "..." }`

#### `POST /api/tools/log-item`
- **Called when**: Agent has confirmed an item deposit or retrieval with the user
- **Input**: `item_name`, `action` ("deposit"/"retrieval"), `user_id`, optional `condition` and `review`
- **Action**: Adds or removes the item from inventory
- **Returns**: `{ success: true, inventory_count: N }`

#### `GET /api/tools/inventory`
- **Called when**: User asks what's available, or agent needs context for a pickup
- **Input**: None
- **Returns**: `{ items: [...] }` — full list of current items with metadata

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

Inventory supports two backends:
- **Supabase mode (preferred):** Uses collaborator schema in `database/schema.sql`.
- **Fallback mode:** In-memory seed data for local testing without DB credentials.

**Methods:**
- `add(name, user_id, condition, review)` — inserts an `items` row (`status='available'`) and logs a `transactions` row.
- `remove(name, user_id)` — marks the first matching available item as `borrowed` (or deletes in legacy schemas) and logs a transaction.
- `list_all()` — returns available items normalized to the API shape used by the dashboard/tool routes.

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
  "inventory": [...]
}
```

Imports the `inventory` singleton directly from `routes/tools` so both share the same in-memory store.

---

## Running the Project

### Prerequisites
- Python 3.10+
- PortAudio system library (`brew install portaudio` on macOS)
- ElevenLabs account with a Conversational AI agent configured
- Anthropic API key (for Pi camera vision, optional on desktop)

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

# Terminal 2: Expose to internet for ElevenLabs webhooks
cloudflared tunnel --url http://localhost:8000

# Terminal 3 (optional): Start a voice conversation directly
python run_conversation.py --user Peter
```

### Dry-Run Dashboard

Once the server is running, open **http://localhost:8000** in your browser. You'll see the dev dashboard — no NFC reader, camera, LEDs, or microphone required.

Walk through the full flow:
1. Click **Peter** under "NFC Tap" — authenticates Peter, **unlocks the door immediately**, and starts the ElevenLabs conversation
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
3. If dropping off: trigger camera to identify item, confirm with user, log it, ask for a mini review
4. If picking up: tell them what's available, let them choose, trigger camera to confirm removal, log it
5. Brief friendly chat, then wrap up
6. When done, call `control_lock("lock")` to close the door — this automatically ends the session.
TOOL USAGE:
- Call `snap_camera_photo` when you need to see what's in the box or identify an item
- Call `log_item` after confirming an item deposit or retrieval with the user
- Call `get_inventory` when the user asks what's available or you need context
- Call `update_user_info` to save nicknames, preferences, or conversation memories
- Call `control_lights` to light up LED positions showing where items are.
  Positions are [row, col] in a 3-row × 10-column grid (both 0-indexed).
- Call `control_lock("lock")` when done — this closes the door AND ends the conversation.
  Do NOT call control_lock("unlock") — the door is already open when you start speaking.
Never fabricate what's in the box. Always use the camera or inventory tools.
Keep conversations SHORT — 3-4 exchanges max unless the user wants to chat.
```

---

## Swapping for Production

| Component | Current (Hackathon) | Production |
|-----------|-------------------|------------|
| Inventory | Supabase (`items` + `transactions`) with in-memory fallback | Same tables, plus stricter validation and monitoring |
| Users | Supabase (`users` + `memories`) | Same tables, plus auth/RLS hardening |
| Camera | Mock (returns "Dune") | `pi_camera.py` with Picamera2 + Anthropic vision |
| LEDs | Mock (console print) | NeoPixel via GPIO |
| Lock | Mock (console print) | Servo via GPIO |
| NFC mapping | Supabase lookup (`nfc_uuid`/`nfc_id` fallback) | Supabase lookup (`nfc_uuid`) |
| Tunnel | cloudflared | cloudflared (same, running on Pi) |

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

The `services/hardware.py` file already auto-detects Pi vs desktop. The remaining TODOs are:

1. **Fill in `pi_leds.py`**: Initialize NeoPixel strip on GPIO pin, implement `set_mode` by mapping `[row, col]` → LED index (`row * 10 + col`) and setting color/animation
2. **Fill in `pi_servo.py`**: Wire servo to a GPIO pin, implement `set_lock` with angle positions for locked/unlocked states
3. **Set up `picamera2`**: Already implemented in `pi_camera.py` — just needs the Pi Camera module connected
4. **NFC reader**: Wire an NFC reader (e.g., PN532) to SPI/I2C, write a small script that calls `POST /api/auth/nfc` when a tag is scanned, then calls `POST /conversation/start`
5. **Run as a service**: Create a systemd unit file so the server starts on boot:
   ```ini
   [Unit]
   Description=Sharing Station
   After=network.target

   [Service]
   WorkingDirectory=/home/pi/sharing-station
   ExecStart=/home/pi/sharing-station/venv/bin/python main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

---

### Step 3 — Raspberry Pi Vibe-Coding Feedback Loop

The goal: make changes on your laptop and see them running on the Pi in seconds.

**Recommended setup:**

1. **VS Code Remote SSH** — install the "Remote - SSH" extension, connect to `pi@raspberrypi.local`, and edit files directly on the Pi. No file sync needed.

2. **`uvicorn --reload`** — run the server in reload mode on the Pi. It watches for file saves and restarts automatically:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **cloudflared stays running** — keep the tunnel alive in a separate terminal so ElevenLabs always hits the same public URL. The server restarts underneath it without breaking the tunnel.

4. **Phone UI as test client** — open `http://raspberrypi.local:8000` on your phone to trigger NFC taps, view inventory, and start/stop conversations without touching physical hardware.

5. **Mock hardware flag** — set `HARDWARE_MOCK=true` in `.env` on the Pi to skip real GPIO calls while iterating on conversation logic. Flip it off only when testing physical hardware.

6. **Quick deploy from laptop** (alternative to Remote SSH):
   ```bash
   rsync -avz --exclude venv --exclude __pycache__ . pi@raspberrypi.local:~/sharing-station/
   ```
   Pair with `uvicorn --reload` on the Pi and changes land in under 2 seconds.
