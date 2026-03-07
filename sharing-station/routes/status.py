from fastapi import APIRouter

from station_state import station
from routes.tools import inventory
from conversation import manager as conversation_manager

router = APIRouter()


@router.get("/status")
async def get_status():
    """
    Polled by the dry-run dashboard every second.
    Returns the full mock station state: conversation, hardware, inventory, event log.
    """
    return {
        "conversation_active": conversation_manager.is_active,
        "lock": station["lock"],
        "led": station["led"],
        "camera": station["camera"],
        "events": station["events"][:40],
        "inventory": inventory.list_all(),
    }
