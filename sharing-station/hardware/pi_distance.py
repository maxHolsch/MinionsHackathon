import time
import RPi.GPIO as GPIO

TRIG = 23
ECHO = 24
CLOSE_THRESHOLD_CM = 30
ECHO_TIMEOUT_S = 0.1  # max time to wait for echo before giving up


class PiDistance:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG, GPIO.OUT)
        GPIO.setup(ECHO, GPIO.IN)
        GPIO.output(TRIG, GPIO.LOW)
        time.sleep(0.5)  # let sensor settle

    def measure_distance(self) -> float:
        """Returns distance in cm, or float('inf') on timeout/error."""
        GPIO.output(TRIG, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG, GPIO.LOW)

        deadline = time.time() + ECHO_TIMEOUT_S

        start = time.time()
        while GPIO.input(ECHO) == 0:
            start = time.time()
            if time.time() > deadline:
                return float("inf")

        stop = time.time()
        while GPIO.input(ECHO) == 1:
            stop = time.time()
            if time.time() > deadline:
                return float("inf")

        return (stop - start) * 34300 / 2

    def is_close(self) -> bool:
        return self.measure_distance() < CLOSE_THRESHOLD_CM

    def cleanup(self):
        GPIO.cleanup()
