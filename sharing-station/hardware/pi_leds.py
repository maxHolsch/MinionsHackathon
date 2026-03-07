import RPi.GPIO as GPIO


# GPIO pins for 3 LED strip rows (30 LEDs each, 90 total)
LED_PINS = [9, 10]  # extend with a third pin for row 3 when wired

TOTAL_LEDS = 90
LEDS_PER_ROW = 30


class PiLEDs:
    """Real GPIO LED controller for the 3-row sharing station grid."""

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        for pin in LED_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        self._lit_rows = {pin: False for pin in LED_PINS}
        print("[PI LEDS] GPIO LED controller initialized")

    def _all_off(self):
        """Turn off all LED rows."""
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.LOW)
            self._lit_rows[pin] = False

    def _set_row(self, row: int, on: bool):
        """Turn a single row on or off (0-indexed)."""
        if row < len(LED_PINS):
            GPIO.output(LED_PINS[row], GPIO.HIGH if on else GPIO.LOW)
            self._lit_rows[LED_PINS[row]] = on

    def set_mode(self, mode: str, position: list = None, color: str = None, slot_count: int = None):
        """Control LEDs based on mode and optional position.

        Modes:
            idle      — all LEDs off (default resting state)
            highlight — light up the row at position[0]
            success   — flash all rows on
            error     — flash all rows on
        """
        count = slot_count or 1

        if mode == "idle":
            self._all_off()
        elif mode == "highlight" and position:
            self._all_off()
            row = position[0]
            self._set_row(row, True)
        elif mode in ("success", "error"):
            for pin in LED_PINS:
                GPIO.output(pin, GPIO.HIGH)
        else:
            self._all_off()

        if position:
            cols = f"{position[1]}-{position[1] + count - 1}" if count > 1 else str(position[1])
            pos_str = f"[row={position[0]}, cols={cols}]"
        else:
            pos_str = "None"
        print(f"[PI LEDS] mode={mode}, position={pos_str}, color={color}")
        return {"success": True, "mode": mode}

    def cleanup(self):
        """Release GPIO resources."""
        self._all_off()
        GPIO.cleanup(LED_PINS)
        print("[PI LEDS] GPIO cleaned up")
