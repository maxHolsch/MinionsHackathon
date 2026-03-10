import os
import urllib.request
import json

from station_state import station, log_event


_pi_ip = os.getenv("PI_IP", "localhost")
PI_URL = f"http://{_pi_ip}" if ":" in _pi_ip else f"http://{_pi_ip}:5000"


class RemoteLEDs:
    """HTTP client that mirrors PiLEDs interface, forwarding calls to the Pi."""

    def __init__(self):
        print(f"[REMOTE LEDS] Connecting to Pi at {PI_URL}")

    def set_mode(self, mode: str, position: list = None, color: str = None, slot_count: int = None):
        count = slot_count or 1
        # Update local station state so the dashboard can see the LED status
        station["led"] = {"mode": mode, "position": position, "color": color, "slot_count": count}
        if position:
            cols = f"{position[1]}-{position[1] + count - 1}" if count > 1 else str(position[1])
            pos_str = f"[row={position[0]}, cols={cols}]"
        else:
            pos_str = "None"
        log_event("LIGHTS", f"mode={mode} pos={pos_str} color={color}")

        payload = {"mode": mode}
        if position is not None:
            payload["position"] = position
        if color is not None:
            payload["color"] = color
        if slot_count is not None:
            payload["slot_count"] = slot_count

        try:
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
        except Exception as e:
            print(f"[REMOTE LEDS] Failed to reach Pi: {e}")
            return {"success": True, "mode": mode}

    def cleanup(self):
        pass
