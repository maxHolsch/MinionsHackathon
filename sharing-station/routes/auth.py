import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import VOICE_RUNTIME
from services.users import UserService
from services.inventory import InventoryService
from services.hardware import servo
from station_state import log_event, set_conversation_state

USE_WEBRTC = VOICE_RUNTIME == "webrtc"

if not USE_WEBRTC:
    from conversation import manager as conversation_manager

router = APIRouter()
users = UserService()
inventory = InventoryService()


class NfcAuthRequest(BaseModel):
    nfc_id: str
    name: str | None = None


@router.post("/nfc")
async def nfc_authenticate(req: NfcAuthRequest):
    """
    Phone calls this when NFC is tapped.
    Looks up the user, unlocks the lock, and prepares/starts conversation context.
    """
    try:
        user, is_new_user = users.get_or_create_by_nfc(req.nfc_id, fallback_name=req.name)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    user_id = user["id"]
    user_name = user.get("name") or "neighbor"
    nickname = user.get("nickname")
    memories = user.get("memories") or []
    preferences = user.get("preferences")
    try:
        contributed_items = [item.get("name") for item in inventory.list_user_contributions(user_id) if item.get("name")]
        checked_out_items = [item.get("name") for item in inventory.list_user_checked_out(user_id) if item.get("name")]
    except RuntimeError:
        contributed_items = []
        checked_out_items = []

    # Unlock the door immediately on NFC tap — no need for an agent tool call
    servo.set_lock("unlock")
    log_event("AUTH", f"NFC auth: {user_name}{' [new]' if is_new_user else ''} → door unlocked")

    if USE_WEBRTC:
        set_conversation_state(
            active=False,
            mic_muted=False,
            mode="webrtc",
            user_id=user_id,
            user_name=user_name,
        )
        log_event("CONV", f"WebRTC session ready for {user_name}")
        conversation_started = False
    else:
        # Start conversation in background so the HTTP response returns immediately
        async def _run_conversation():
            try:
                await asyncio.to_thread(
                    conversation_manager.start,
                    user_id=user_id,
                    user_name=user_name,
                    nickname=nickname,
                    memories=memories,
                    preferences=preferences,
                    contributed_items=contributed_items,
                    checked_out_items=checked_out_items,
                    is_new_user=is_new_user,
                )
            except Exception as e:
                conversation_manager.is_active = False
                log_event("ERROR", f"Conversation failed: {e}")

        asyncio.create_task(_run_conversation())
        conversation_started = True

    return {
        "authenticated": True,
        "user_id": user_id,
        "user_name": user_name,
        "nickname": nickname,
        "memories": memories,
        "preferences": preferences,
        "contributed_items": contributed_items,
        "checked_out_items": checked_out_items,
        "is_new_user": is_new_user,
        "conversation_mode": VOICE_RUNTIME,
        "conversation_started": conversation_started,
    }
