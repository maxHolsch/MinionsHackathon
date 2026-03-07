from fastapi import APIRouter

from config import VOICE_RUNTIME
from station_state import station, set_conversation_state
from routes.tools import inventory

USE_WEBRTC = VOICE_RUNTIME == "webrtc"

if not USE_WEBRTC:
    from conversation import manager as conversation_manager

router = APIRouter()


@router.get("/status")
async def get_status():
    """
    Polled by the dry-run dashboard every second.
    Returns the full mock station state: conversation, hardware, inventory, event log.
    """
    try:
        inventory_items = inventory.list_all()
        checked_out_items = inventory.list_checked_out()
        inventory_error = None
    except RuntimeError as e:
        inventory_items = []
        checked_out_items = []
        inventory_error = str(e)

    conversation_state = station.get("conversation", {})
    if USE_WEBRTC:
        conversation_active = bool(conversation_state.get("active"))
    else:
        conversation_active = conversation_manager.is_active
        set_conversation_state(active=conversation_active, mode="python")
        conversation_state = station.get("conversation", {})

    return {
        "conversation_active": conversation_active,
        "conversation_mode": VOICE_RUNTIME,
        "mic_muted": bool(conversation_state.get("mic_muted", False)),
        "lock": station["lock"],
        "led": station["led"],
        "camera": station["camera"],
        "events": station["events"][:40],
        "inventory": inventory_items,
        "checked_out": checked_out_items,
        "inventory_error": inventory_error,
    }
