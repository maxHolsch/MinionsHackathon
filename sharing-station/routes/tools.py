import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from config import VOICE_RUNTIME
from services.inventory import InventoryService
from services.users import UserService
from services.hardware import camera, leds, servo
from station_state import log_event, set_conversation_state

USE_WEBRTC = VOICE_RUNTIME == "webrtc"

if not USE_WEBRTC:
    from conversation import manager as conversation_manager

router = APIRouter()
inventory = InventoryService()
users = UserService()


class CameraRequest(BaseModel):
    reason: str
    prompt: Optional[str] = None  # Custom vision prompt for the AI


class LogItemRequest(BaseModel):
    item_name: str
    action: str  # "deposit" or "retrieval"
    user_id: str
    condition: Optional[str] = None
    review: Optional[str] = None
    slot_row: Optional[int] = None  # Physical row (0-2) in 3×10 grid
    slot_col: Optional[int] = None  # Physical col (0-9) in 3×10 grid


class UserInfoRequest(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    memory: Optional[str] = None
    preferences: Optional[str] = None


class LightsRequest(BaseModel):
    mode: str
    position: Optional[List[int]] = None  # [row, col] — 3 rows × 10 cols (0-indexed)
    color: Optional[str] = None


class LockRequest(BaseModel):
    action: str  # "unlock" or "lock"


@router.post("/camera")
async def snap_camera(req: CameraRequest):
    """Takes a photo and identifies items using vision AI."""
    print(f"[CAMERA] Triggered: {req.reason}")
    result = camera.capture_and_identify(req.reason, req.prompt)
    return result


@router.post("/log-item")
async def log_item(req: LogItemRequest):
    """Logs item deposit or retrieval."""
    try:
        if req.action == "deposit":
            item = inventory.add(req.item_name, req.user_id, req.condition, req.review, req.slot_row, req.slot_col)
            pos = item.get("position")
            log_event("LOG", f"Deposited '{req.item_name}' by {req.user_id} → slot {pos}")
        elif req.action == "retrieval":
            inventory.remove(req.item_name, req.user_id)
            log_event("LOG", f"Retrieved '{req.item_name}' by {req.user_id}")
        count = len(inventory.list_all())
        return {"success": True, "inventory_count": count}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"log-item failed: {e}")


@router.get("/inventory")
async def get_inventory():
    """Returns current inventory."""
    print("[INVENTORY] Requested")
    try:
        return {"items": inventory.list_all()}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/available-slots")
async def get_available_slots():
    """Returns available physical slot positions in the 3x10 grid."""
    print("[SLOTS] Available slots requested")
    try:
        slots = inventory.get_available_slots()
        return {"available_slots": slots, "total_available": len(slots)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/user-info")
async def update_user_info(req: UserInfoRequest):
    """Updates user information."""
    print(f"[USER] Update: {req.user_id} — nickname={req.nickname}, memory={req.memory}")
    try:
        users.update(req.user_id, req.nickname, req.memory, req.preferences)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"success": True}


@router.post("/lights")
async def control_lights(req: LightsRequest):
    """Controls LED lights inside the station."""
    print(f"[LIGHTS] mode={req.mode}, position={req.position}, color={req.color}")
    result = leds.set_mode(req.mode, req.position, req.color)
    return result


@router.post("/lock")
async def control_lock(req: LockRequest):
    """Controls the door lock. Locking re-engages the door and ends the conversation."""
    print(f"[LOCK] {req.action}")
    result = servo.set_lock(req.action)
    if req.action == "lock":
        if USE_WEBRTC:
            set_conversation_state(active=False, mic_muted=False)
            log_event("CONV", "Session ended after lock action")
        else:
            # End the conversation after the response is returned
            async def _end_conversation():
                await asyncio.sleep(0.5)
                await asyncio.to_thread(conversation_manager.stop)
            asyncio.create_task(_end_conversation())
    return result
