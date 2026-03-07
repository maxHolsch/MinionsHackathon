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
