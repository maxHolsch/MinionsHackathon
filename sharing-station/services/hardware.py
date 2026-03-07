import os


def is_raspberry_pi():
    """Detect if running on Pi."""
    return os.path.exists("/sys/firmware/devicetree/base/model")


if is_raspberry_pi():
    from hardware.pi_camera import PiCamera
    from hardware.pi_leds import PiLEDs
    from hardware.pi_servo import PiServo
else:
    from hardware.mock_camera import MockCamera as PiCamera
    from hardware.mock_leds import MockLEDs as PiLEDs
    from hardware.mock_servo import MockServo as PiServo

camera = PiCamera()
leds = PiLEDs()
servo = PiServo()
