import sys
import termios
import time
import tty

import RPi.GPIO as GPIO


SERVO_PIN = 14
LOCK_ANGLE = 0       # degrees — door locked
UNLOCK_ANGLE = 90    # degrees — door unlocked
NUDGE_STEP = 5       # degrees per arrow key press


class PiServo:
    """Real servo controller via GPIO PWM for the station door lock."""

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SERVO_PIN, GPIO.OUT)
        self._pwm = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz for servo
        self._pwm.start(0)
        self._current_angle = LOCK_ANGLE
        print("[PI SERVO] GPIO PWM servo controller initialized")

    def _set_angle(self, angle: int):
        """Rotate servo to the given angle (0-270).

        Duty cycle mapping: 2.5% = 0°, 12.5% = 270°.
        """
        angle = max(0, min(270, angle))
        duty = 2.5 + (angle / 270.0) * 10.0
        self._pwm.ChangeDutyCycle(duty)
        time.sleep(0.5)          # wait for movement
        self._pwm.ChangeDutyCycle(0)  # stop signal to prevent jitter
        self._current_angle = angle

    def set_lock(self, action: str):
        """Lock or unlock the station door.

        action: "lock" rotates to 0°, "unlock" rotates to 90°.
        """
        if action == "lock":
            self._set_angle(LOCK_ANGLE)
            state = "locked"
        else:
            self._set_angle(UNLOCK_ANGLE)
            state = "unlocked"
        print(f"[PI SERVO] Door {state}")
        return {"success": True, "state": state}

    def nudge(self, direction: int):
        """Nudge servo by NUDGE_STEP degrees. direction: -1 (left) or +1 (right)."""
        new_angle = self._current_angle + direction * NUDGE_STEP
        new_angle = max(0, min(270, new_angle))
        self._set_angle(new_angle)
        print(f"[PI SERVO] Nudged to {new_angle}°")
        return {"success": True, "angle": new_angle}

    def debug_keyboard(self):
        """Interactive debug: left/right arrow keys nudge servo, 'q' quits."""
        print("[PI SERVO] Debug mode — Left/Right arrows to nudge, 'q' to quit")
        print(f"  Current angle: {self._current_angle}°  Step: {NUDGE_STEP}°")
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    break
                if ch == '\x1b':  # escape sequence (arrow keys)
                    seq = sys.stdin.read(2)
                    if seq == '[D':  # left arrow
                        self.nudge(-1)
                    elif seq == '[C':  # right arrow
                        self.nudge(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print(f"\n[PI SERVO] Debug ended at {self._current_angle}°")

    def cleanup(self):
        """Release PWM and GPIO resources."""
        self._pwm.stop()
        GPIO.cleanup(SERVO_PIN)
        print("[PI SERVO] GPIO cleaned up")
