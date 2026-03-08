"""Run on the Pi to test which GPIO pins control the LEDs.

Usage: python test_gpio_pins.py
"""

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

# All usable BCM GPIO pins on Pi 3
test_pins = [2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 17, 18, 22, 23, 24, 25, 27]

print("Testing each GPIO pin for 2 seconds. Watch which one lights the LEDs.\n")

for pin in test_pins:
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        print(f"  BCM {pin:2d} → HIGH   (watching...)")
        time.sleep(2)
        GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"  BCM {pin:2d} → SKIP   ({e})")

GPIO.cleanup()
print("\nDone. Which pin(s) lit up the LEDs?")
