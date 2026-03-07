class MockLEDs:
    """Mock LED controller that prints state to console."""

    def set_mode(self, mode: str, position: list = None, color: str = None):
        # position is [row, col] in a 3-row × 10-col grid
        pos_str = f"[row={position[0]}, col={position[1]}]" if position else "None"
        print(f"[MOCK LEDS] mode={mode}, position={pos_str}, color={color}")
        return {"success": True, "mode": mode}
