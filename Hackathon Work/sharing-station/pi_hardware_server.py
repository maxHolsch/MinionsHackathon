"""Lightweight Flask server for Raspberry Pi hardware control.

Run this on the Pi. The laptop sends HTTP requests to control servos and LEDs.

Usage:
    pip install flask RPi.GPIO
    python pi_hardware_server.py
"""

from flask import Flask, request, jsonify
from hardware.pi_servo import PiServo
from hardware.pi_leds import PiLEDs
from hardware.pi_distance import PiDistance

app = Flask(__name__)
servo = PiServo()
leds = PiLEDs()
distance = PiDistance()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "device": "raspberry_pi"})


@app.route("/servo", methods=["POST"])
def servo_control():
    data = request.json
    action = data.get("action", "lock")
    result = servo.set_lock(action)
    return jsonify(result)


@app.route("/light", methods=["POST"])
def light_control():
    data = request.json
    mode = data.get("mode", "idle")
    position = data.get("position")
    color = data.get("color")
    slot_count = data.get("slot_count")
    result = leds.set_mode(mode, position, color, slot_count=slot_count)
    return jsonify(result)


@app.route("/distance", methods=["GET"])
def distance_check():
    cm = distance.measure_distance()
    close = distance.is_close()
    return jsonify({"distance_cm": cm, "is_close": close})


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000)
    finally:
        servo.cleanup()
        leds.cleanup()
        distance.cleanup()
