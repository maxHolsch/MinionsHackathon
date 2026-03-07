class PiServo:
    """Real servo controller via GPIO for door lock. Implement when on Pi."""

    def __init__(self):
        # TODO: Initialize servo via GPIO
        print("[PI SERVO] Servo controller initialized")

    def set_lock(self, action: str):
        # TODO: Implement real servo control
        print(f"[PI SERVO] Lock action: {action}")
        return {"success": True, "state": action + "ed"}
