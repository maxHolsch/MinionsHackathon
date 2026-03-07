import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.users import UserService
from services.hardware import servo
from conversation import manager as conversation_manager
from station_state import log_event

router = APIRouter()
users = UserService()


class NfcAuthRequest(BaseModel):
    nfc_id: str


@router.post("/nfc")
async def nfc_authenticate(req: NfcAuthRequest):
    """
    Phone calls this when NFC is tapped.
    Looks up the user, then auto-starts the conversation with full context.
    """
    try:
        user, is_new_user = users.get_or_create_by_nfc(req.nfc_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    user_id = user["id"]
    user_name = user.get("name") or "neighbor"
    nickname = user.get("nickname")
    memories = user.get("memories") or []

    # Unlock the door immediately on NFC tap — no need for an agent tool call
    servo.set_lock("unlock")
    log_event("AUTH", f"NFC auth: {user_name}{' [new]' if is_new_user else ''} → door unlocked")

    # Start conversation in background so the HTTP response returns immediately
    async def _run_conversation():
        try:
            await asyncio.to_thread(
                conversation_manager.start,
                user_id=user_id,
                user_name=user_name,
                nickname=nickname,
                memories=memories,
                is_new_user=is_new_user,
            )
        except Exception as e:
            conversation_manager.is_active = False
            log_event("ERROR", f"Conversation failed: {e}")

    asyncio.create_task(_run_conversation())

    return {
        "authenticated": True,
        "user_id": user_id,
        "user_name": user_name,
        "nickname": nickname,
        "is_new_user": is_new_user,
        "conversation_started": True,
    }
