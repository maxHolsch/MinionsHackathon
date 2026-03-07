from station_state import station, log_event


class MockServo:
    """Mock servo controller that prints lock state to console."""

    def set_lock(self, action: str):
        new_state = "locked" if action == "lock" else "unlocked"
        station["lock"] = new_state
        log_event("LOCK", f"Door {new_state}")
        return {"success": True, "state": new_state}
