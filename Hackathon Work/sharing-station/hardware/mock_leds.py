from station_state import station, log_event


class MockLEDs:
    """Mock LED controller that prints state to console."""

    def set_mode(self, mode: str, position: list = None, color: str = None, slot_count: int = None):
        # position is [row, col] in a 3-row × 10-col grid
        count = slot_count or 1
        station["led"] = {"mode": mode, "position": position, "color": color, "slot_count": count}
        if position:
            cols = f"{position[1]}-{position[1] + count - 1}" if count > 1 else str(position[1])
            pos_str = f"[row={position[0]}, cols={cols}]"
        else:
            pos_str = "None"
        log_event("LIGHTS", f"mode={mode} pos={pos_str} color={color}")
        return {"success": True, "mode": mode}
