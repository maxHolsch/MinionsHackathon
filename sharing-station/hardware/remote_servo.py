import os
import urllib.request
import json


PI_URL = f"http://{os.getenv('PI_IP', 'localhost')}:5000"


class RemoteServo:
    """HTTP client that mirrors PiServo interface, forwarding calls to the Pi."""

    def __init__(self):
        print(f"[REMOTE SERVO] Connecting to Pi at {PI_URL}")

    def set_lock(self, action: str):
        data = json.dumps({"action": action}).encode()
        req = urllib.request.Request(
            f"{PI_URL}/servo",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(f"[REMOTE SERVO] {action} → {result}")
        return result

    def cleanup(self):
        pass
