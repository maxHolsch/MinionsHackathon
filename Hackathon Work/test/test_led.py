import RPi.GPIO as GPIO

# GPIO pins for 3 LED strip rows (22 LEDs each, total 66 LEDs)
LED_PINS = [9, 10]  # extend if you have a third GPIO pin for row 3

# We treat 66 LEDs as a flat sequence across 3 rows of 22
TOTAL_LEDS = 90
LEDS_PER_ROW = 30

# Each "LED" here is abstracted; in practice you'd drive a strip via
# a single GPIO per row (e.g. NeoPixel/WS2812 via a library).
# This script uses RPi.GPIO to demonstrate the logic with simple on/off pins.
# Replace GPIO.output calls with your actual strip library if needed.

GPIO.setmode(GPIO.BCM)
for pin in LED_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Track how many LEDs are lit (cursor position)
lit_count = 0  # number of LEDs currently lit from position 0

def update_leds(count):
    """Light up 'count' LEDs from the start of the strip."""
    # Row 1: GPIO 9 (LEDs 1-22)
    # Row 2: GPIO 10 (LEDs 23-44)
    # Row 3: (would need a third pin) (LEDs 45-66)
    row1 = min(count, LEDS_PER_ROW)
    row2 = min(max(count - LEDS_PER_ROW, 0), LEDS_PER_ROW)
    row3 = min(max(count - 2 * LEDS_PER_ROW, 0), LEDS_PER_ROW)

    GPIO.output(LED_PINS[0], GPIO.HIGH if row1 > 0 else GPIO.LOW)
    GPIO.output(LED_PINS[1], GPIO.HIGH if row2 > 0 else GPIO.LOW)
    # GPIO.output(LED_PINS[2], GPIO.HIGH if row3 > 0 else GPIO.LOW)

    print(f"LEDs lit: {count} / {TOTAL_LEDS}  "
          f"(row1={row1}, row2={row2}, row3={row3})")

print("LED Strip test — GPIO 9 (row 1), GPIO 10 (row 2)")
print("  <number> -> light up that many MORE LEDs from current position")
print("  Q        -> turn off all LEDs")
print("  q        -> quit")

try:
    while True:
        key = input("Enter command: ").strip()
        if key.upper() == 'Q':
            lit_count = 0
            update_leds(0)
            print("All LEDs turned off.")
        elif key.lower() == 'q':
            break
        else:
            try:
                n = int(key)
                if n <= 0:
                    print("Enter a positive number.")
                    continue
                new_count = lit_count + n
                if new_count > TOTAL_LEDS:
                    print(f"Only {TOTAL_LEDS - lit_count} LEDs remaining. "
                          f"Lighting all remaining.")
                    new_count = TOTAL_LEDS
                lit_count = new_count
                update_leds(lit_count)
            except ValueError:
                print("Unknown command. Enter a number, Q to clear, or q to quit.")
finally:
    for pin in LED_PINS:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up.")
