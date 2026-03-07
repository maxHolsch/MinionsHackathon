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
    try:
        inventory_items = inventory.list_all()
        checked_out_items = inventory.list_checked_out()
        inventory_error = None
    except RuntimeError as e:
        inventory_items = []
        checked_out_items = []
        inventory_error = str(e)

    return {
        "conversation_active": conversation_manager.is_active,
        "lock": station["lock"],
        "led": station["led"],
        "camera": station["camera"],
        "events": station["events"][:40],
        "inventory": inventory_items,
        "checked_out": checked_out_items,
        "inventory_error": inventory_error,
    }
