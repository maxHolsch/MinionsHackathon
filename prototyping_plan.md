# Minions Sharing Station — Prototyping Plan

## Phase 1: Agent on Desktop with Tool Calls

Goal: ElevenLabs agent running on your laptop, personality working, all tool calls firing reliably against mock implementations.

---

### Step 1.1 — ElevenLabs Agent Setup (Dashboard)

Create the agent at elevenlabs.io/app/conversational-ai/agents:

**LLM**: Claude (Sonnet or Haiku for speed during testing, Sonnet for demo)

**First message**:
```
Hey there, sugar! Welcome back to the sharing station! Tap your phone so I know who I'm talking to!
```

**System prompt** (starting point — iterate on this):
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
1. User authenticates via NFC → you receive their name and history via dynamic variables
2. Ask what they're doing (dropping off or picking up)
3. If dropping off: trigger camera to identify item, confirm with user, log it, ask for a mini review
4. If picking up: tell them what's available, let them choose, trigger camera to confirm removal, log it
5. Brief friendly chat, then wrap up

TOOL USAGE:
- Call `snap_camera_photo` when you need to see what's in the box or identify an item
- Call `log_item` after confirming an item deposit or retrieval with the user
- Call `get_inventory` when the user asks what's available or you need context
- Call `update_user_info` to save nicknames, preferences, or conversation memories
- Call `control_lights` to light up LED positions showing where items are
- Call `control_lock` to unlock/lock the door after authentication

Never fabricate what's in the box. Always use the camera or inventory tools.
Keep conversations SHORT — 3-4 exchanges max unless the user wants to chat.
```

---

### Step 1.2 — Define All Server Tools

Configure these in the ElevenLabs dashboard under your agent's Tools section.
Point all webhook URLs at your local FastAPI server (tunneled via cloudflared).

#### Tool 1: `snap_camera_photo`
```
Name: snap_camera_photo
Description: Takes a photo with the station camera and uses AI vision to identify
  items in the box. Call this when a user says they've placed something in or
  taken something out, or when you need to verify the box contents.
Type: Webhook (Server Tool)
Method: POST
URL: {your_tunnel_url}/api/tools/camera
Body parameters:
  - reason (string, required): Why the photo is being taken.
    e.g. "user deposited an item" or "verifying pickup"
Response: Returns JSON with identified items and descriptions.
```

#### Tool 2: `log_item`
```
Name: log_item
Description: Logs an item being deposited into or retrieved from the sharing station.
  Call this AFTER confirming with the user what the item is and whether they're
  dropping off or picking up.
Type: Webhook (Server Tool)
Method: POST
URL: {your_tunnel_url}/api/tools/log-item
Body parameters:
  - item_name (string, required): Name of the item. e.g. "Settlers of Catan", "Dune by Frank Herbert"
  - action (string, required): Either "deposit" or "retrieval"
  - user_id (string, required): The authenticated user's ID
  - condition (string, optional): Brief note on item condition
  - review (string, optional): User's mini review or comment about the item
```

#### Tool 3: `get_inventory`
```
Name: get_inventory
Description: Gets the current list of items available in the sharing station.
  Call this when a user asks what's available, or at the start of a pickup
  conversation to know what you can offer.
Type: Webhook (Server Tool)
Method: GET
URL: {your_tunnel_url}/api/tools/inventory
No parameters needed.
Response: Returns JSON array of items with names, who deposited them, and any reviews.
```

#### Tool 4: `update_user_info`
```
Name: update_user_info
Description: Saves information about a user for future interactions — like their
  preferred nickname, what they like to read, or a memorable moment from conversation.
  Call this when you learn something worth remembering about the user.
Type: Webhook (Server Tool)
Method: POST
URL: {your_tunnel_url}/api/tools/user-info
Body parameters:
  - user_id (string, required): The user's ID
  - nickname (string, optional): Affectionate nickname you've given them
  - memory (string, optional): Something to remember for next time
  - preferences (string, optional): What they like (genres, games, etc.)
```

#### Tool 5: `control_lights`
```
Name: control_lights
Description: Controls the LED lights inside the sharing station box. Use to
  highlight where specific items are located, or to set a mood/status color.
Type: Webhook (Server Tool)
Method: POST
URL: {your_tunnel_url}/api/tools/lights
Body parameters:
  - mode (string, required): One of "highlight_item", "welcome", "goodbye", "idle", "error"
  - position (integer, optional): Item position to highlight (1-6). Only used with highlight_item mode.
  - color (string, optional): Hex color code. e.g. "#FF6B35"
```

#### Tool 6: `control_lock`
```
Name: control_lock
Description: Controls the door lock of the sharing station. Call this to unlock
  the door after a user has been authenticated, or to lock it when they're done.
Type: Webhook (Server Tool)
Method: POST
URL: {your_tunnel_url}/api/tools/lock
Body parameters:
  - action (string, required): Either "unlock" or "lock"
```

---

### Step 1.3 — FastAPI Mock Server (Desktop)

This is what you run on your laptop first. All tools return mock data.
Later you'll swap in real hardware calls and Supabase.

```
sharing-station/
├── main.py              # FastAPI app + ElevenLabs conversation runner
├── routes/
│   ├── tools.py         # All 6 tool endpoints
│   └── auth.py          # NFC auth endpoint (phone calls this)
├── services/
│   ├── inventory.py     # In-memory inventory (swap for Supabase later)
│   ├── vision.py        # Camera + Anthropic vision (mock first)
│   ├── hardware.py      # LED/servo control (mock first, GPIO later)
│   └── users.py         # In-memory user store (swap for Supabase later)
├── conversation.py      # ElevenLabs session management
├── config.py            # Environment variables
└── requirements.txt
```

**requirements.txt:**
```
fastapi
uvicorn
elevenlabs
anthropic
python-dotenv
```

**main.py:**
```python
import os
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from routes.tools import router as tools_router
from routes.auth import router as auth_router
from conversation import ConversationManager

conversation_manager = ConversationManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🟢 Sharing Station server starting...")
    yield
    # Shutdown
    print("🔴 Shutting down...")
    conversation_manager.stop()

app = FastAPI(title="Sharing Station", lifespan=lifespan)
app.include_router(tools_router, prefix="/api/tools")
app.include_router(auth_router, prefix="/api/auth")

@app.get("/health")
async def health():
    return {"status": "ok", "conversation_active": conversation_manager.is_active}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**routes/tools.py (mock implementations):**
```python
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from services.inventory import InventoryService
from services.users import UserService

router = APIRouter()
inventory = InventoryService()
users = UserService()


class CameraRequest(BaseModel):
    reason: str

class LogItemRequest(BaseModel):
    item_name: str
    action: str  # "deposit" or "retrieval"
    user_id: str
    condition: Optional[str] = None
    review: Optional[str] = None

class UserInfoRequest(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    memory: Optional[str] = None
    preferences: Optional[str] = None

class LightsRequest(BaseModel):
    mode: str
    position: Optional[int] = None
    color: Optional[str] = None

class LockRequest(BaseModel):
    action: str  # "unlock" or "lock"


@router.post("/camera")
async def snap_camera(req: CameraRequest):
    """Mock: returns a fake item identification."""
    print(f"📸 Camera triggered: {req.reason}")
    # In production: capture image, send to Anthropic vision
    return {
        "items_detected": [
            {"name": "Dune by Frank Herbert", "type": "book", "condition": "good"}
        ],
        "raw_description": "A paperback copy of Dune by Frank Herbert, slightly worn spine"
    }


@router.post("/log-item")
async def log_item(req: LogItemRequest):
    """Logs item deposit or retrieval."""
    print(f"📦 Item log: {req.action} '{req.item_name}' by user {req.user_id}")
    if req.action == "deposit":
        inventory.add(req.item_name, req.user_id, req.condition, req.review)
    elif req.action == "retrieval":
        inventory.remove(req.item_name, req.user_id)
    return {"success": True, "inventory_count": len(inventory.items)}


@router.get("/inventory")
async def get_inventory():
    """Returns current inventory."""
    print("📋 Inventory requested")
    return {"items": inventory.list_all()}


@router.post("/user-info")
async def update_user_info(req: UserInfoRequest):
    """Updates user information."""
    print(f"👤 User update: {req.user_id} - nickname={req.nickname}, memory={req.memory}")
    users.update(req.user_id, req.nickname, req.memory, req.preferences)
    return {"success": True}


@router.post("/lights")
async def control_lights(req: LightsRequest):
    """Mock: prints LED state."""
    print(f"💡 LEDs: mode={req.mode}, position={req.position}, color={req.color}")
    return {"success": True, "mode": req.mode}


@router.post("/lock")
async def control_lock(req: LockRequest):
    """Mock: prints lock state."""
    print(f"🔒 Lock: {req.action}")
    return {"success": True, "state": req.action + "ed"}
```

**services/inventory.py:**
```python
from datetime import datetime

class InventoryService:
    """In-memory inventory. Swap for Supabase later."""

    def __init__(self):
        # Pre-seed with some items for testing
        self.items = [
            {
                "id": "1",
                "name": "Settlers of Catan",
                "type": "board_game",
                "deposited_by": "peter",
                "deposited_at": "2025-03-06T10:00:00Z",
                "condition": "good, all pieces present",
                "review": "Great game, got tired of it after 20 plays though!"
            },
            {
                "id": "2",
                "name": "The Great Gatsby",
                "type": "book",
                "deposited_by": "alice",
                "deposited_at": "2025-03-05T14:00:00Z",
                "condition": "slightly dog-eared",
                "review": None
            }
        ]
        self._next_id = 3

    def add(self, name, user_id, condition=None, review=None):
        item = {
            "id": str(self._next_id),
            "name": name,
            "type": "unknown",
            "deposited_by": user_id,
            "deposited_at": datetime.utcnow().isoformat() + "Z",
            "condition": condition,
            "review": review
        }
        self.items.append(item)
        self._next_id += 1
        return item

    def remove(self, name, user_id):
        self.items = [i for i in self.items if i["name"].lower() != name.lower()]

    def list_all(self):
        return self.items
```

**services/users.py:**
```python
class UserService:
    """In-memory user store. Swap for Supabase later."""

    def __init__(self):
        self.users = {
            "peter": {
                "name": "Peter",
                "nickname": "Tiger",
                "memories": ["Loves sci-fi books", "Plays Catan every Thursday"],
                "preferences": "science fiction, strategy games"
            },
            "alice": {
                "name": "Alice",
                "nickname": None,
                "memories": [],
                "preferences": None
            }
        }

    def get(self, user_id):
        return self.users.get(user_id)

    def update(self, user_id, nickname=None, memory=None, preferences=None):
        if user_id not in self.users:
            self.users[user_id] = {"name": user_id, "nickname": None, "memories": [], "preferences": None}
        user = self.users[user_id]
        if nickname:
            user["nickname"] = nickname
        if memory:
            user["memories"].append(memory)
        if preferences:
            user["preferences"] = preferences
```

**conversation.py:**
```python
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

class ConversationManager:
    def __init__(self):
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.conversation = None
        self.is_active = False

    def start(self, user_id: str = None, user_name: str = None):
        """Start a new conversation session."""
        dynamic_vars = {}
        if user_name:
            dynamic_vars["user_name"] = user_name

        config = ConversationInitiationData(dynamic_variables=dynamic_vars)

        self.conversation = Conversation(
            self.client,
            self.agent_id,
            config=config,
            requires_auth=bool(os.getenv("ELEVENLABS_API_KEY")),
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda r: print(f"🤖 Agent: {r}"),
            callback_agent_response_correction=lambda o, c: print(f"🤖 Agent: {o} → {c}"),
            callback_user_transcript=lambda t: print(f"🎤 User: {t}"),
        )
        self.conversation.start_session()
        self.is_active = True
        print(f"🟢 Conversation started for user: {user_name or 'unknown'}")

    def stop(self):
        if self.conversation:
            self.conversation.end_session()
            self.conversation.wait_for_session_end()
            self.is_active = False
            print("🔴 Conversation ended")

    def wait(self):
        if self.conversation:
            self.conversation.wait_for_session_end()
```

**routes/auth.py:**
```python
from fastapi import APIRouter
from pydantic import BaseModel
from services.users import UserService

router = APIRouter()
users = UserService()

class NfcAuthRequest(BaseModel):
    nfc_id: str

@router.post("/nfc")
async def nfc_authenticate(req: NfcAuthRequest):
    """Phone calls this when NFC is tapped."""
    # Map NFC ID to user (hardcoded for hackathon)
    nfc_to_user = {
        "abc123": "peter",
        "def456": "alice",
        "ghi789": "bob"
    }
    user_id = nfc_to_user.get(req.nfc_id)
    if not user_id:
        return {"authenticated": False, "error": "Unknown NFC tag"}

    user = users.get(user_id)
    return {
        "authenticated": True,
        "user_id": user_id,
        "user_name": user["name"] if user else user_id,
        "nickname": user.get("nickname") if user else None
    }
```

---

### Step 1.4 — Run It

```bash
# Terminal 1: Start the server
cd sharing-station
pip install -r requirements.txt
ELEVENLABS_API_KEY=your_key ELEVENLABS_AGENT_ID=your_agent_id python main.py

# Terminal 2: Expose via tunnel
cloudflared tunnel --url http://localhost:8000

# Copy the tunnel URL, paste into all your ElevenLabs tool webhook URLs

# Terminal 3: Start a conversation (or add a CLI entry point)
python -c "
from conversation import ConversationManager
cm = ConversationManager()
cm.start(user_name='Peter')
cm.wait()
"
```

---

### Step 1.5 — Testing Checklist

Test each scenario by talking to the agent:

- [ ] **"I'm dropping off a book"** → agent calls `snap_camera_photo`, then `log_item` with action=deposit
- [ ] **"What's available?"** → agent calls `get_inventory`, reads back items
- [ ] **"I want to pick up Catan"** → agent calls `get_inventory`, then `snap_camera_photo` to confirm, then `log_item` with action=retrieval
- [ ] **"I thought the book was great"** → agent calls `update_user_info` with a memory or calls `log_item` with a review
- [ ] **Agent gives you a nickname** → calls `update_user_info` with nickname
- [ ] **Agent greets returning user** → uses dynamic variables to know who you are

**If tool calls aren't firing reliably:**
- Make tool descriptions more explicit about WHEN to call them
- Add examples in the description: "For example, call this when user says 'I'm putting something in'"
- Check that parameter names match exactly between dashboard config and your Pydantic models
- Try a more capable LLM (Claude Sonnet over Haiku)

---

## Phase 2: Wrap for Pi Compatibility

Goal: Same codebase runs on Raspberry Pi with real hardware hooks.

### Step 2.1 — Abstract Hardware

Replace mock returns with a hardware abstraction layer:

```python
# services/hardware.py
import os
import platform

def is_raspberry_pi():
    """Detect if running on Pi."""
    return os.path.exists("/sys/firmware/devicetree/base/model")

if is_raspberry_pi():
    from hardware.pi_camera import PiCamera
    from hardware.pi_leds import PiLEDs
    from hardware.pi_servo import PiServo
else:
    from hardware.mock_camera import MockCamera as PiCamera
    from hardware.mock_leds import MockLEDs as PiLEDs
    from hardware.mock_servo import MockServo as PiServo

camera = PiCamera()
leds = PiLEDs()
servo = PiServo()
```

### Step 2.2 — Audio

The ElevenLabs Python SDK `DefaultAudioInterface` uses PyAudio.
On desktop it uses your laptop mic/speakers.
On Pi it uses whatever ALSA device is configured — your wired mic and speaker.

Test on Pi:
```bash
# Check audio devices
arecord -l   # list capture devices
aplay -l     # list playback devices

# Test
arecord -d 3 test.wav && aplay test.wav
```

If audio device selection is wrong, you may need a custom AudioInterface
that specifies the device index. Cross that bridge on the Pi.

### Step 2.3 — Camera (Real)

```python
# hardware/pi_camera.py
import base64
from picamera2 import Picamera2
from anthropic import Anthropic

class PiCamera:
    def __init__(self):
        self.cam = Picamera2()
        self.cam.configure(self.cam.create_still_configuration())
        self.anthropic = Anthropic()

    def capture_and_identify(self, reason: str) -> dict:
        self.cam.start()
        self.cam.capture_file("/tmp/station_photo.jpg")
        self.cam.stop()

        with open("/tmp/station_photo.jpg", "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": f"You are the vision system for a community sharing station. "
                     f"Identify any items (books, board games, objects) visible in this image. "
                     f"Context: {reason}. "
                     f"Return JSON: {{\"items_detected\": [{{\"name\": \"...\", \"type\": \"book|board_game|other\", \"condition\": \"...\"}}], \"raw_description\": \"...\"}}"
                    }
                ]
            }]
        )
        # Parse the response
        import json
        try:
            return json.loads(response.content[0].text)
        except:
            return {"items_detected": [], "raw_description": response.content[0].text}
```

### Step 2.4 — File Structure (Final)

```
sharing-station/
├── main.py
├── config.py
├── conversation.py
├── requirements.txt
├── routes/
│   ├── tools.py
│   └── auth.py
├── services/
│   ├── inventory.py      # In-memory → Supabase later
│   ├── users.py           # In-memory → Supabase later
│   └── hardware.py        # Auto-detects Pi vs desktop
├── hardware/
│   ├── mock_camera.py     # Returns fake identifications
│   ├── mock_leds.py       # Prints to console
│   ├── mock_servo.py      # Prints to console
│   ├── pi_camera.py       # picamera2 + Anthropic vision
│   ├── pi_leds.py         # NeoPixel via GPIO
│   └── pi_servo.py        # Servo via GPIO
└── static/
    └── index.html         # Phone UI (later)
```

---

## Tool Call Summary

| Tool | When Agent Calls It | Returns |
|------|-------------------|---------|
| `snap_camera_photo` | User deposits/retrieves item, or agent needs to verify | Item identifications from vision AI |
| `log_item` | After confirming item + action with user | Success + inventory count |
| `get_inventory` | User asks what's available, or start of pickup flow | List of current items |
| `update_user_info` | Agent learns something about user (nickname, preference) | Success |
| `control_lights` | Welcome animation, item highlighting, goodbye | Success + mode |
| `control_lock` | After NFC auth (unlock) or end of interaction (lock) | Success + state |

---

## Key Decisions

- **All tools are server tools (webhooks)** — simplest, everything goes through your FastAPI server
- **In-memory stores for Phase 1** — swap `InventoryService` and `UserService` for `supabase-py` later without changing the routes
- **Hardware auto-detection** — same codebase runs mock on desktop, real on Pi
- **No Vercel** — Pi + cloudflared is the entire backend
- **Camera → Anthropic vision** — ElevenLabs doesn't do vision, so camera captures go through your server to Anthropic's API, result fed back to the ElevenLabs agent via tool response
