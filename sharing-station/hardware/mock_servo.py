class MockServo:
    """Mock servo controller that prints lock state to console."""

    def set_lock(self, action: str):
        print(f"[MOCK SERVO] Lock action: {action}")
        return {"success": True, "state": action + "ed"}
