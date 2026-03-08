from station_state import station, log_event


class MockServo:
    """Mock servo controller that prints lock state to console."""

    def __init__(self):
        self._current_angle = 0

    def set_lock(self, action: str):
        new_state = "locked" if action == "lock" else "unlocked"
        self._current_angle = 0 if action == "lock" else 90
        station["lock"] = new_state
        log_event("LOCK", f"Door {new_state}")
        return {"success": True, "state": new_state}

    def nudge(self, direction: int):
        self._current_angle = max(0, min(270, self._current_angle + direction * 5))
        log_event("LOCK", f"Nudged to {self._current_angle}°")
        return {"success": True, "angle": self._current_angle}

    def debug_keyboard(self):
        print("[MOCK SERVO] debug_keyboard not available in mock mode")

    def cleanup(self):
        pass
