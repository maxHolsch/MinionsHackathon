from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services.inventory import InventoryService
from services.users import UserService
from services.hardware import camera, leds, servo

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
    """Takes a photo and identifies items using vision AI."""
    print(f"[CAMERA] Triggered: {req.reason}")
    result = camera.capture_and_identify(req.reason)
    return result


@router.post("/log-item")
async def log_item(req: LogItemRequest):
    """Logs item deposit or retrieval."""
    print(f"[LOG] {req.action} '{req.item_name}' by user {req.user_id}")
    if req.action == "deposit":
        inventory.add(req.item_name, req.user_id, req.condition, req.review)
    elif req.action == "retrieval":
        inventory.remove(req.item_name, req.user_id)
    return {"success": True, "inventory_count": len(inventory.items)}


@router.get("/inventory")
async def get_inventory():
    """Returns current inventory."""
    print("[INVENTORY] Requested")
    return {"items": inventory.list_all()}


@router.post("/user-info")
async def update_user_info(req: UserInfoRequest):
    """Updates user information."""
    print(f"[USER] Update: {req.user_id} — nickname={req.nickname}, memory={req.memory}")
    users.update(req.user_id, req.nickname, req.memory, req.preferences)
    return {"success": True}


@router.post("/lights")
async def control_lights(req: LightsRequest):
    """Controls LED lights inside the station."""
    print(f"[LIGHTS] mode={req.mode}, position={req.position}, color={req.color}")
    result = leds.set_mode(req.mode, req.position, req.color)
    return result


@router.post("/lock")
async def control_lock(req: LockRequest):
    """Controls the door lock."""
    print(f"[LOCK] {req.action}")
    result = servo.set_lock(req.action)
    return result
