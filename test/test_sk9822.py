"""
SK9822 LED strip test — GPIO 10 (data) / GPIO 11 (clock)
90 LEDs, 3 rows x 10 cols x 3 LEDs per slot.

Run on Pi:
    python test/test_sk9822.py

Controls:
    1  — fill entire strip red
    2  — fill entire strip green
    3  — fill entire strip blue
    4  — fill entire strip amber (default slot colour)
    7  — fill entire strip orange (#fc9403)
    5  — chase: light up each slot one by one across all rows
    6  — highlight a specific slot  (prompts for row and col)
    d  — set brightness (0–31, current shown in prompt)
    c  — clear (all off)
    q  — quit
"""
import sys
import time

try:
    from apa102_pi.driver.apa102 import APA102
except ImportError:
    print("apa102-pi not installed. Run: pip install apa102-pi")
    sys.exit(1)

NUM_LEDS      = 90
LEDS_PER_ROW  = 30
COLS_PER_ROW  = 10
LEDS_PER_SLOT = LEDS_PER_ROW // COLS_PER_ROW  # 3

AMBER  = (245, 166,  35)
ORANGE = (252, 148,   3)  # #fc9403
RED    = (255,   0,   0)
GREEN  = (  0, 255,  80)
BLUE   = (  0,  80, 255)
WHITE  = (255, 200, 100)


def slot_indices(row, col, count=1):
    start = row * LEDS_PER_ROW + col * LEDS_PER_SLOT
    end   = row * LEDS_PER_ROW + (col + count) * LEDS_PER_SLOT
    return range(start, min(end, (row + 1) * LEDS_PER_ROW))


def fill(strip, r, g, b):
    for i in range(NUM_LEDS):
        strip.set_pixel(i, r, g, b)
    strip.show()


def clear(strip):
    strip.clear_strip()


def chase(strip):
    print("Chase — lighting each slot in sequence...")
    clear(strip)
    for row in range(3):
        for col in range(COLS_PER_ROW):
            for i in slot_indices(row, col):
                strip.set_pixel(i, *AMBER)
            strip.show()
            print(f"  slot [{row},{col}]")
            time.sleep(0.12)
    time.sleep(0.5)
    clear(strip)
    print("Done.")


def highlight_slot(strip):
    try:
        row = int(input("  Row (0-2): ").strip())
        col = int(input("  Col (0-9): ").strip())
    except ValueError:
        print("  Invalid input.")
        return
    if not (0 <= row <= 2 and 0 <= col <= 9):
        print("  Out of range.")
        return
    clear(strip)
    for i in slot_indices(row, col):
        strip.set_pixel(i, *AMBER)
    strip.show()
    print(f"  Highlighted slot [{row},{col}] — press c to clear")


strip = APA102(num_led=NUM_LEDS, global_brightness=31, order="rgb")
clear(strip)
print("SK9822 strip ready (90 LEDs, GPIO 10/11)")
print(__doc__)

try:
    while True:
        cmd = input("Command: ").strip().lower()
        if cmd == "1":
            fill(strip, *RED)
            print("Red")
        elif cmd == "2":
            fill(strip, *GREEN)
            print("Green")
        elif cmd == "3":
            fill(strip, *BLUE)
            print("Blue")
        elif cmd == "4":
            fill(strip, *AMBER)
            print("Amber")
        elif cmd == "7":
            fill(strip, *ORANGE)
            print("Orange")
        elif cmd == "5":
            chase(strip)
        elif cmd == "6":
            highlight_slot(strip)
        elif cmd == "d":
            try:
                val = int(input(f"  Brightness 0-31 (current={strip.global_brightness}): ").strip())
                val = max(0, min(31, val))
                strip.global_brightness = val
                strip.show()
                print(f"  Brightness set to {val}")
            except ValueError:
                print("  Invalid input.")
        elif cmd == "c":
            clear(strip)
            print("Cleared")
        elif cmd == "q":
            break
        else:
            print("Unknown command")
finally:
    clear(strip)
    strip.cleanup()
    print("Cleaned up.")
