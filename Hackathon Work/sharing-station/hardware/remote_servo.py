import os
import urllib.request
import json


_pi_ip = os.getenv("PI_IP", "localhost")
PI_URL = f"http://{_pi_ip}" if ":" in _pi_ip else f"http://{_pi_ip}:5000"


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

    def nudge(self, direction: int):
        data = json.dumps({"direction": direction}).encode()
        req = urllib.request.Request(
            f"{PI_URL}/servo/nudge",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(f"[REMOTE SERVO] nudge {direction} → {result}")
        return result

    def cleanup(self):
        pass
