import RPi.GPIO as GPIO
import time

TRIG = 23
ECHO = 24
CLOSE_THRESHOLD_CM = 30

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.output(TRIG, GPIO.LOW)

print("Ultrasonic distance sensor test — TRIG=GPIO23, ECHO=GPIO24")
print("Threshold: 30 cm  |  Ctrl+C to quit")
time.sleep(0.5)

def measure_distance():
    # Send 10us trigger pulse
    GPIO.output(TRIG, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG, GPIO.LOW)

    # Wait for echo start
    start = time.time()
    while GPIO.input(ECHO) == 0:
        start = time.time()

    # Wait for echo end
    stop = time.time()
    while GPIO.input(ECHO) == 1:
        stop = time.time()

    # Distance = (travel time * speed of sound) / 2
    elapsed = stop - start
    distance_cm = (elapsed * 34300) / 2
    return distance_cm

try:
    while True:
        distance = measure_distance()
        if distance < CLOSE_THRESHOLD_CM:
            print(f"Found you!  ({distance:.1f} cm)")
        else:
            print(f"Nothing Detected  ({distance:.1f} cm)")
        time.sleep(0.5)
finally:
    GPIO.cleanup()
    print("GPIO cleaned up.")
