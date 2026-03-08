"""
Shared in-memory state for the mock hardware layer.
Mock camera/leds/servo write here; the /api/status endpoint reads it.
On a real Pi, the Pi hardware classes bypass this entirely.
"""

from datetime import datetime

station = {
    "lock": "locked",
    "led": {"mode": "idle", "position": None, "color": None},
    "camera": None,
    "conversation": {
        "active": False,
        "mic_muted": False,
        "mode": "webrtc",
        "user_id": None,
        "user_name": None,
    },
    "pending_user": None,  # set by poller when a new active user is detected; cleared by browser after it starts the session
    "distance": {"cm": None, "is_close": None, "asleep": None},
    "events": [],
}


def log_event(category: str, message: str, data=None):
    event = {
        "t": datetime.now().strftime("%H:%M:%S"),
        "category": category,
        "message": message,
        "data": data,
    }
    station["events"].insert(0, event)
    if len(station["events"]) > 100:
        station["events"].pop()


def set_conversation_state(
    active=None,
    mic_muted=None,
    mode=None,
    user_id=None,
    user_name=None,
):
    conversation = station.setdefault(
        "conversation",
        {"active": False, "mic_muted": False, "mode": "webrtc", "user_id": None, "user_name": None},
    )
    if active is not None:
        conversation["active"] = bool(active)
    if mic_muted is not None:
        conversation["mic_muted"] = bool(mic_muted)
    if mode is not None:
        conversation["mode"] = mode
    if user_id is not None:
        conversation["user_id"] = user_id
    if user_name is not None:
        conversation["user_name"] = user_name
    return conversation
