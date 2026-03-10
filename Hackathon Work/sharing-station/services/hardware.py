import os


PI_IP = os.getenv("PI_IP")


def is_raspberry_pi():
    """Detect if running on Pi."""
    return os.path.exists("/sys/firmware/devicetree/base/model")


if PI_IP:
    # Remote mode: servo/LEDs/distance on Pi over HTTP, camera local
    from hardware.remote_servo import RemoteServo as PiServo
    from hardware.remote_leds import RemoteLEDs as PiLEDs
    from hardware.remote_distance import RemoteDistance as PiDistance
    try:
        import cv2  # noqa: F401
        from hardware.usb_camera import USBCamera as PiCamera
    except ImportError:
        from hardware.mock_camera import MockCamera as PiCamera
    print(f"[HARDWARE] Remote mode — Pi at {PI_IP}, camera local")
elif is_raspberry_pi():
    from hardware.pi_camera import PiCamera
    from hardware.pi_leds import PiLEDs
    from hardware.pi_servo import PiServo
    from hardware.pi_distance import PiDistance
else:
    # Use real USB camera with Claude vision when opencv is available
    try:
        import cv2  # noqa: F401
        from hardware.usb_camera import USBCamera as PiCamera
    except ImportError:
        from hardware.mock_camera import MockCamera as PiCamera
    from hardware.mock_leds import MockLEDs as PiLEDs
    from hardware.mock_servo import MockServo as PiServo
    from hardware.mock_distance import MockDistance as PiDistance

camera = PiCamera()
leds = PiLEDs()
servo = PiServo()
distance = PiDistance()
