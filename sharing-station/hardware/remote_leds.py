import os
import urllib.request
import json


_pi_ip = os.getenv("PI_IP", "localhost")
PI_URL = f"http://{_pi_ip}" if ":" in _pi_ip else f"http://{_pi_ip}:5000"


class RemoteLEDs:
    """HTTP client that mirrors PiLEDs interface, forwarding calls to the Pi."""

    def __init__(self):
        print(f"[REMOTE LEDS] Connecting to Pi at {PI_URL}")

    def set_mode(self, mode: str, position: list = None, color: str = None, slot_count: int = None):
        payload = {"mode": mode}
        if position is not None:
            payload["position"] = position
        if color is not None:
            payload["color"] = color
        if slot_count is not None:
            payload["slot_count"] = slot_count

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{PI_URL}/light",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(f"[REMOTE LEDS] {mode} → {result}")
        return result

    def cleanup(self):
        pass
