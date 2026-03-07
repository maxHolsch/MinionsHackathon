import RPi.GPIO as GPIO
import time

SERVO_PIN = 14

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)

# 50Hz PWM for servo
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)

def set_angle(angle):
    # Duty cycle: 2.5% = 0 deg, 12.5% = 270 deg
    duty = 2.5 + (angle / 270.0) * 10.0
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)  # stop jitter

print("Servo test on GPIO 14")
print("  1 -> move to 270 degrees")
print("  2 -> move to 0 degrees")
print("  q -> quit")

try:
    while True:
        key = input("Enter command: ").strip().lower()
        if key == '1':
            print("Moving to 270 degrees...")
            set_angle(270)
        elif key == '2':
            print("Moving to 0 degrees...")
            set_angle(0)
        elif key == 'q':
            break
        else:
            print("Unknown command. Use 1, 2, or q.")
finally:
    pwm.stop()
    GPIO.cleanup()
    print("GPIO cleaned up.")
