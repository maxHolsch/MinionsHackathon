import os
import urllib.request
import json


_pi_ip = os.getenv("PI_IP", "localhost")
PI_URL = f"http://{_pi_ip}" if ":" in _pi_ip else f"http://{_pi_ip}:5000"


class RemoteDistance:
    """HTTP client that mirrors PiDistance interface, forwarding calls to the Pi."""

    def __init__(self):
        print(f"[REMOTE DISTANCE] Connecting to Pi at {PI_URL}")

    def measure_distance(self) -> float:
        req = urllib.request.Request(f"{PI_URL}/distance", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        return result.get("distance_cm", float("inf"))

    def is_close(self) -> bool:
        req = urllib.request.Request(f"{PI_URL}/distance", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        return result.get("is_close", False)

    def cleanup(self):
        pass
