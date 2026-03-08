import RPi.GPIO as GPIO
import time

SERVO_PIN = 14

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)

pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)


def set_angle(angle):
    """Move servo to angle (0-270). Duty: 2.5% = 0°, 12.5% = 270°."""
    duty = 2.5 + (angle / 270.0) * 10.0
    print(f"  -> angle={angle}°  duty={duty:.2f}%")
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)


print("=== Servo Calibration Tool ===")
print(f"Pin: GPIO {SERVO_PIN}")
print()
print("Commands:")
print("  <number>    - move to that angle (0-270)")
print("  sweep       - sweep from 0 to 270 in steps of 15")
print("  fine <a> <b> - sweep from a to b in steps of 5")
print("  q           - quit")
print()
print("Tip: note the angles where the door is fully open/closed.")
print()

try:
    while True:
        cmd = input("servo> ").strip().lower()
        if cmd == 'q':
            break
        elif cmd == 'sweep':
            for angle in range(0, 271, 15):
                set_angle(angle)
                resp = input(f"  angle={angle}° — press Enter to continue, 's' to stop: ").strip()
                if resp == 's':
                    break
        elif cmd.startswith('fine'):
            parts = cmd.split()
            if len(parts) == 3:
                a, b = int(parts[1]), int(parts[2])
                step = 5 if a < b else -5
                for angle in range(a, b + (1 if step > 0 else -1), step):
                    set_angle(angle)
                    resp = input(f"  angle={angle}° — Enter=next, 's'=stop: ").strip()
                    if resp == 's':
                        break
            else:
                print("Usage: fine <start> <end>  (e.g. fine 60 120)")
        else:
            try:
                angle = int(cmd)
                if 0 <= angle <= 270:
                    set_angle(angle)
                else:
                    print("Angle must be 0-270")
            except ValueError:
                print("Unknown command. Enter an angle (0-270), 'sweep', 'fine <a> <b>', or 'q'.")
finally:
    pwm.stop()
    GPIO.cleanup()
    print("GPIO cleaned up.")
