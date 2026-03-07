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
        "ghi789": "bob",
    }
    user_id = nfc_to_user.get(req.nfc_id)
    if not user_id:
        return {"authenticated": False, "error": "Unknown NFC tag"}

    user = users.get(user_id)
    return {
        "authenticated": True,
        "user_id": user_id,
        "user_name": user["name"] if user else user_id,
        "nickname": user.get("nickname") if user else None,
    }
