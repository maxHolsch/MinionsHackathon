from station_state import station, log_event


class MockLEDs:
    """Mock LED controller that prints state to console."""

    def set_mode(self, mode: str, position: list = None, color: str = None):
        # position is [row, col] in a 3-row × 10-col grid
        station["led"] = {"mode": mode, "position": position, "color": color}
        pos_str = f"[row={position[0]}, col={position[1]}]" if position else "None"
        log_event("LIGHTS", f"mode={mode} pos={pos_str} color={color}")
        return {"success": True, "mode": mode}
