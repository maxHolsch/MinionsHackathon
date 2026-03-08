from apa102_pi.driver.apa102 import APA102

# Hardware SPI: GPIO 10 = MOSI (data), GPIO 11 = SCLK (clock)
NUM_LEDS = 90
LEDS_PER_ROW = 30
COLS_PER_ROW = 10
LEDS_PER_SLOT = LEDS_PER_ROW // COLS_PER_ROW  # 3 LEDs per grid slot

DEFAULT_COLOR = (245, 166, 35)   # amber
WELCOME_COLOR = (255, 200, 100)  # warm white
SUCCESS_COLOR = (0, 255, 80)
ERROR_COLOR   = (255, 0, 0)


def _parse_color(hex_color: str | None) -> tuple:
    """Parse a hex color string like '#f5a623' into an (r, g, b) tuple."""
    if not hex_color:
        return DEFAULT_COLOR
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return DEFAULT_COLOR
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return DEFAULT_COLOR


def _slot_indices(row: int, col: int, count: int = 1) -> range:
    """Return the LED indices for a slot (or span of slots)."""
    start = row * LEDS_PER_ROW + col * LEDS_PER_SLOT
    end   = row * LEDS_PER_ROW + (col + count) * LEDS_PER_SLOT
    return range(start, min(end, (row + 1) * LEDS_PER_ROW))


class PiLEDs:
    """SK9822/APA102 LED controller over hardware SPI (GPIO 10 / 11)."""

    def __init__(self):
        self._strip = APA102(num_led=NUM_LEDS, global_brightness=31, order="rgb")
        self._clear()
        print("[PI LEDS] SK9822 strip initialised (GPIO 10/11, 90 LEDs)")

    def _clear(self):
        self._strip.clear_strip()

    def _fill(self, r: int, g: int, b: int):
        for i in range(NUM_LEDS):
            self._strip.set_pixel(i, r, g, b)
        self._strip.show()

    def set_mode(self, mode: str, position: list = None, color: str = None, slot_count: int = None):
        count = slot_count or 1
        rgb   = _parse_color(color)

        if mode == "idle":
            self._clear()

        elif mode == "highlight_item" and position:
            self._clear()
            for i in _slot_indices(position[0], position[1], count):
                self._strip.set_pixel(i, *rgb)
            self._strip.show()

        elif mode == "welcome":
            self._fill(*WELCOME_COLOR)

        elif mode == "goodbye":
            self._clear()

        elif mode == "success":
            self._fill(*SUCCESS_COLOR)

        elif mode == "error":
            self._fill(*ERROR_COLOR)

        else:
            self._clear()

        if position:
            cols = f"{position[1]}-{position[1] + count - 1}" if count > 1 else str(position[1])
            pos_str = f"[row={position[0]}, cols={cols}]"
        else:
            pos_str = "None"
        print(f"[PI LEDS] mode={mode}, position={pos_str}, color={color}")
        return {"success": True, "mode": mode}

    def cleanup(self):
        self._clear()
        self._strip.cleanup()
        print("[PI LEDS] cleanup done")
