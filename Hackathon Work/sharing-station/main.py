from contextlib import asynccontextmanager
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from config import ELEVENLABS_AGENT_ID, ELEVENLABS_API_KEY, VOICE_RUNTIME
from database.client import supabase as _supabase
from routes.tools import router as tools_router
from routes.auth import router as auth_router
from routes.status import router as status_router
from services.inventory import InventoryService
from services.users import UserService
from services.hardware import servo, distance
from station_state import log_event, set_conversation_state, station

USE_WEBRTC = VOICE_RUNTIME == "webrtc"

if not USE_WEBRTC:
    from conversation import manager as conversation_manager

_users = UserService()
_inventory = InventoryService()


async def _poll_active_user():
    last_user_id = None
    while True:
        try:
            if _supabase:
                res = await asyncio.to_thread(_supabase.functions.invoke, "get-active-user")
                if isinstance(res, (bytes, str)):
                    user_data = json.loads(res) if res else None
                else:
                    user_data = res.data if res else None
                current_id = user_data.get("id") if isinstance(user_data, dict) else None

                if current_id != last_user_id:
                    last_user_id = current_id

                    if current_id:
                        # New active user detected — mirror NFC auth flow
                        try:
                            user = await asyncio.to_thread(_users.get, current_id)
                        except Exception:
                            user = None

                        user_name = (user.get("name") if user else None) or user_data.get("name") or "neighbor"
                        nickname = (user.get("nickname") if user else None) or user_data.get("nickname")
                        memories = (user.get("memories") if user else None) or []
                        preferences = (user.get("preferences") if user else None)

                        try:
                            contributed_items = [
                                item.get("name")
                                for item in await asyncio.to_thread(_inventory.list_user_contributions, current_id)
                                if item.get("name")
                            ]
                            checked_out_items = [
                                item.get("name")
                                for item in await asyncio.to_thread(_inventory.list_user_checked_out, current_id)
                                if item.get("name")
                            ]
                        except Exception:
                            contributed_items = []
                            checked_out_items = []

                        await asyncio.to_thread(servo.set_lock, "unlock")
                        log_event("AUTH", f"Active user detected: {user_name} → door unlocked")

                        if USE_WEBRTC:
                            station["pending_user"] = {
                                "user_id": current_id,
                                "user_name": user_name,
                                "nickname": nickname,
                                "memories": memories,
                                "preferences": preferences,
                                "contributed_items": contributed_items,
                                "checked_out_items": checked_out_items,
                                "is_new_user": False,
                            }
                            log_event("CONV", f"WebRTC session pending for {user_name}")
                        else:
                            _uid, _uname, _nick, _mem, _prefs, _contrib, _checkout = (
                                current_id, user_name, nickname, memories,
                                preferences, contributed_items, checked_out_items,
                            )

                            async def _run_conversation():
                                try:
                                    await asyncio.to_thread(
                                        conversation_manager.start,
                                        user_id=_uid,
                                        user_name=_uname,
                                        nickname=_nick,
                                        memories=_mem,
                                        preferences=_prefs,
                                        contributed_items=_contrib,
                                        checked_out_items=_checkout,
                                        is_new_user=False,
                                    )
                                except Exception as e:
                                    conversation_manager.is_active = False
                                    log_event("ERROR", f"Conversation failed: {e}")

                            asyncio.create_task(_run_conversation())

                    else:
                        # Active user cleared — stop conversation and lock door
                        log_event("AUTH", "Active user cleared → stopping conversation")
                        station["pending_user"] = None
                        if USE_WEBRTC:
                            set_conversation_state(active=False, mic_muted=False, mode="webrtc")
                        else:
                            await asyncio.to_thread(conversation_manager.stop)
                        await asyncio.to_thread(servo.set_lock, "lock")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[POLL] get-active-user error: {e}")

        await asyncio.sleep(5)


async def _keyboard_servo_listener():
    """Background task: left/right arrow keys nudge the servo from the terminal."""
    if not sys.stdin.isatty():
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    print("[KEYBOARD] Servo debug: Left/Right arrows to nudge, no quit (runs alongside server)")
    try:
        tty.setcbreak(fd)  # cbreak so Ctrl-C still works
        while True:
            ch = await asyncio.to_thread(sys.stdin.read, 1)
            if ch == '\x1b':
                seq = await asyncio.to_thread(sys.stdin.read, 2)
                if seq == '[D':  # left arrow
                    await asyncio.to_thread(servo.nudge, -1)
                elif seq == '[C':  # right arrow
                    await asyncio.to_thread(servo.nudge, 1)
    except asyncio.CancelledError:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("[KEYBOARD] Servo debug listener stopped")


async def _poll_distance_sensor():
    """Poll distance sensor — station never sleeps, always stays awake."""
    _awake_written = False

    while True:
        try:
            cm = await asyncio.to_thread(distance.measure_distance)
            close = cm < 30  # same threshold as PiDistance.CLOSE_THRESHOLD_CM

            station["distance"]["cm"] = round(cm, 1) if cm != float("inf") else None
            station["distance"]["is_close"] = close
            station["distance"]["asleep"] = False

            if not _awake_written:
                _awake_written = True
                if _supabase:
                    await asyncio.to_thread(
                        lambda: _supabase.table("station_config")
                            .update({"station_asleep": False})
                            .eq("id", 1)
                            .execute()
                    )
                log_event("INFO", "Distance: station always-on mode — never sleeping")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[DISTANCE] Error: {e}")

        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[SERVER] Sharing Station server starting...")
    if _supabase:
        try:
            await asyncio.to_thread(_supabase.functions.invoke, "deactivate-user")
            print("[SERVER] Cleared any active users from previous session")
        except Exception as e:
            print(f"[SERVER] Failed to deactivate users on startup: {e}")
    poll_task = asyncio.create_task(_poll_active_user())
    distance_task = asyncio.create_task(_poll_distance_sensor())
    keyboard_task = asyncio.create_task(_keyboard_servo_listener())
    yield
    # Shutdown
    poll_task.cancel()
    distance_task.cancel()
    keyboard_task.cancel()
    distance.cleanup()
    print("[SERVER] Shutting down...")
    if not USE_WEBRTC:
        conversation_manager.stop()


app = FastAPI(title="Sharing Station", lifespan=lifespan)
app.include_router(tools_router, prefix="/api/tools")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(status_router, prefix="/api")


@app.get("/health")
async def health():
    if USE_WEBRTC:
        conversation_active = bool(station.get("conversation", {}).get("active"))
    else:
        conversation_active = conversation_manager.is_active
    return {
        "status": "ok",
        "voice_runtime": VOICE_RUNTIME,
        "conversation_active": conversation_active,
    }


class ConversationMicRequest(BaseModel):
    muted: bool


class ConversationStateRequest(BaseModel):
    active: bool | None = None
    mic_muted: bool | None = None
    user_id: str | None = None
    user_name: str | None = None


def _fetch_webrtc_token() -> str:
    if not ELEVENLABS_AGENT_ID:
        raise HTTPException(status_code=500, detail="ELEVENLABS_AGENT_ID is missing")
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is missing")

    token_url = (
        "https://api.elevenlabs.io/v1/convai/conversation/token"
        f"?agent_id={quote(ELEVENLABS_AGENT_ID)}"
    )
    request = Request(token_url, headers={"xi-api-key": ELEVENLABS_API_KEY}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs token request failed ({e.code}): {body}",
        )
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach ElevenLabs: {e}")

    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=502, detail=f"Token missing in ElevenLabs response: {payload}")
    return token


@app.post("/conversation/token")
async def get_conversation_token():
    """
    Returns credentials for browser-side WebRTC session startup.
    Keeps API key server-side so Pi/browser clients stay simple.
    """
    if not ELEVENLABS_AGENT_ID:
        raise HTTPException(status_code=500, detail="ELEVENLABS_AGENT_ID is missing")

    if ELEVENLABS_API_KEY:
        conversation_token = _fetch_webrtc_token()
        return {
            "conversation_token": conversation_token,
            "agent_id": ELEVENLABS_AGENT_ID,
            "connection_type": "webrtc",
            "mode": "private",
            "voice_runtime": VOICE_RUNTIME,
        }

    # Public agents can start directly with just agent_id.
    return {
        "agent_id": ELEVENLABS_AGENT_ID,
        "connection_type": "webrtc",
        "mode": "public",
        "voice_runtime": VOICE_RUNTIME,
    }


@app.post("/conversation/state")
async def set_conversation_state_endpoint(req: ConversationStateRequest):
    """
    Browser client updates session state here (active, mic muted, current user).
    Useful for dashboard/status visibility in WebRTC mode.
    """
    state = set_conversation_state(
        active=req.active,
        mic_muted=req.mic_muted,
        user_id=req.user_id,
        user_name=req.user_name,
        mode=VOICE_RUNTIME,
    )
    return {"status": "ok", "voice_runtime": VOICE_RUNTIME, "conversation": state}


@app.post("/conversation/mic")
async def set_conversation_mic(req: ConversationMicRequest):
    state = set_conversation_state(mic_muted=req.muted, mode=VOICE_RUNTIME)
    return {"status": "ok", "voice_runtime": VOICE_RUNTIME, "mic_muted": state["mic_muted"]}


@app.post("/conversation/start")
async def start_conversation(user_name: str = "Unknown", user_id: str = None,
                              nickname: str = None, is_new_user: bool = False):
    """Start a conversation session (for testing via API — NFC auth auto-starts in production)."""
    from services.users import UserService
    users = UserService()
    inventory = InventoryService()
    try:
        user = users.get(user_id) if user_id else None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    resolved_user_name = user_name
    if user and (not user_name or user_name == "Unknown"):
        resolved_user_name = user.get("name") or user_name
    memories = user.get("memories") or [] if user else []
    preferences = user.get("preferences") if user else None
    nickname = nickname or (user.get("nickname") if user else None)
    contributed_items = []
    checked_out_items = []
    if user_id:
        try:
            contributed_items = [item.get("name") for item in inventory.list_user_contributions(user_id) if item.get("name")]
            checked_out_items = [item.get("name") for item in inventory.list_user_checked_out(user_id) if item.get("name")]
        except RuntimeError:
            contributed_items = []
            checked_out_items = []

    if USE_WEBRTC:
        set_conversation_state(
            active=False,
            mic_muted=False,
            user_id=user_id,
            user_name=resolved_user_name,
            mode=VOICE_RUNTIME,
        )
        return {
            "status": "ready",
            "voice_runtime": VOICE_RUNTIME,
            "user": resolved_user_name,
            "user_id": user_id,
            "nickname": nickname,
            "memories": memories,
            "preferences": preferences,
            "contributed_items": contributed_items,
            "checked_out_items": checked_out_items,
            "is_new_user": is_new_user,
            "conversation_started": False,
        }

    conversation_manager.start(
        user_name=resolved_user_name,
        user_id=user_id,
        nickname=nickname,
        memories=memories,
        preferences=preferences,
        contributed_items=contributed_items,
        checked_out_items=checked_out_items,
        is_new_user=is_new_user,
    )
    set_conversation_state(active=True, user_id=user_id, user_name=resolved_user_name, mode="python")
    return {"status": "started", "voice_runtime": "python", "user": resolved_user_name, "is_new_user": is_new_user}


@app.post("/conversation/stop")
async def stop_conversation():
    """Stop the current conversation session."""
    users = UserService()
    try:
        await asyncio.to_thread(users.deactivate_all)
    except Exception as e:
        print(f"[SERVER] Failed to deactivate users on stop: {e}")
    station["pending_user"] = None

    if USE_WEBRTC:
        set_conversation_state(active=False, mic_muted=False, mode="webrtc")
        return {"status": "stopped", "voice_runtime": "webrtc"}

    conversation_manager.stop()
    set_conversation_state(active=False, mic_muted=False, mode="python")
    return {"status": "stopped", "voice_runtime": "python"}



# Static files mount LAST — it's a catch-all on "/"
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
