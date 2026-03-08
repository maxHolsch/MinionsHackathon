"""
HC-SR04 ultrasonic distance sensor test — TRIG=GPIO23, ECHO=GPIO24
Threshold: 30 cm

Run on Pi:
    python test/test_distance.py

Ctrl+C to quit.
"""
import time
import RPi.GPIO as GPIO

TRIG = 23
ECHO = 24
CLOSE_THRESHOLD_CM = 30
ECHO_TIMEOUT_S = 0.1  # if no echo within 100ms, report sensor error


GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.output(TRIG, GPIO.LOW)
print("Settling...")
time.sleep(0.5)
print("Ready. Measuring every 0.5s — Ctrl+C to quit.\n")


def measure_distance():
    """Returns distance in cm, or None on timeout."""
    GPIO.output(TRIG, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG, GPIO.LOW)

    deadline = time.time() + ECHO_TIMEOUT_S

    start = time.time()
    while GPIO.input(ECHO) == 0:
        start = time.time()
        if time.time() > deadline:
            return None

    stop = time.time()
    while GPIO.input(ECHO) == 1:
        stop = time.time()
        if time.time() > deadline:
            return None

    return (stop - start) * 34300 / 2


try:
    while True:
        distance = measure_distance()
        if distance is None:
            print("⚠  Sensor timeout — check wiring (TRIG=GPIO23, ECHO=GPIO24)")
        elif distance < CLOSE_THRESHOLD_CM:
            print(f"✓  Detected  {distance:.1f} cm  (< {CLOSE_THRESHOLD_CM} cm threshold)")
        else:
            print(f"   Clear     {distance:.1f} cm")
        time.sleep(0.5)
finally:
    GPIO.cleanup()
    print("\nGPIO cleaned up.")
