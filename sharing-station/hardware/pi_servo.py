import time

import RPi.GPIO as GPIO


SERVO_PIN = 14
LOCK_ANGLE = 0       # degrees — door locked
UNLOCK_ANGLE = 270   # degrees — door unlocked


class PiServo:
    """Real servo controller via GPIO PWM for the station door lock."""

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SERVO_PIN, GPIO.OUT)
        self._pwm = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz for servo
        self._pwm.start(0)
        print("[PI SERVO] GPIO PWM servo controller initialized")

    def _set_angle(self, angle: int):
        """Rotate servo to the given angle (0-270).

        Duty cycle mapping: 2.5% = 0°, 12.5% = 270°.
        """
        duty = 2.5 + (angle / 270.0) * 10.0
        self._pwm.ChangeDutyCycle(duty)
        time.sleep(0.5)          # wait for movement
        self._pwm.ChangeDutyCycle(0)  # stop signal to prevent jitter

    def set_lock(self, action: str):
        """Lock or unlock the station door.

        action: "lock" rotates to 0°, "unlock" rotates to 270°.
        """
        if action == "lock":
            self._set_angle(LOCK_ANGLE)
            state = "locked"
        else:
            self._set_angle(UNLOCK_ANGLE)
            state = "unlocked"
        print(f"[PI SERVO] Door {state}")
        return {"success": True, "state": state}

    def cleanup(self):
        """Release PWM and GPIO resources."""
        self._pwm.stop()
        GPIO.cleanup(SERVO_PIN)
        print("[PI SERVO] GPIO cleaned up")
