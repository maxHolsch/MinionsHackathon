class MockLEDs:
    """Mock LED controller that prints state to console."""

    def set_mode(self, mode: str, position: int = None, color: str = None):
        print(f"[MOCK LEDS] mode={mode}, position={position}, color={color}")
        return {"success": True, "mode": mode}
