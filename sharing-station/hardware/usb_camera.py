import base64
import json

import cv2
from anthropic import Anthropic

from station_state import station, log_event

DEFAULT_VISION_PROMPT = (
    "You are the vision system for a community sharing station. "
    "Identify any items (books, board games, objects) visible in this image. "
    "Context: {reason}. "
    "For each item, estimate how many grid slots (each ~10cm wide) it needs to sit flat. "
    "Guidelines: a paperback book ≈ 2 slots, a large hardcover ≈ 3, a board game box ≈ 6-8, a small accessory ≈ 1. "
    'Return JSON: {{"items_detected": [{{"name": "...", "type": "book|board_game|other", "condition": "...", "estimated_size": "small|medium|large", "slots_needed": <int>}}], "raw_description": "..."}}'
)


class USBCamera:
    """USB camera with Anthropic vision for item identification."""

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.anthropic = Anthropic()

    def capture_and_identify(self, reason: str, prompt: str = None) -> dict:
        cap = cv2.VideoCapture(self.device_index)
        if not cap.isOpened():
            log_event("CAMERA", f"USB camera not available — {reason}")
            return {
                "items_detected": [],
                "raw_description": "Camera not available.",
            }

        try:
            # Grab a few frames to let auto-exposure settle
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            if not ret:
                log_event("CAMERA", f"Failed to capture frame — {reason}")
                return {
                    "items_detected": [],
                    "raw_description": "Failed to capture image.",
                }

            # Encode frame to JPEG in memory
            success, buf = cv2.imencode(".jpg", frame)
            if not success:
                return {
                    "items_detected": [],
                    "raw_description": "Failed to encode image.",
                }

            image_data = base64.standard_b64encode(buf.tobytes()).decode("utf-8")
        finally:
            cap.release()

        vision_prompt = prompt or DEFAULT_VISION_PROMPT.format(reason=reason)
        if prompt:
            vision_prompt = f"Context: {reason}.\n\n{prompt}"

        print(f"[CAMERA] Sending image to Claude vision... (reason: {reason})")
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": vision_prompt,
                        },
                    ],
                }
            ],
        )

        raw_text = response.content[0].text
        print(f"[CAMERA] Claude raw response: {raw_text}")

        result = None
        try:
            result = json.loads(raw_text)
        except (json.JSONDecodeError, IndexError):
            result = {
                "items_detected": [],
                "raw_description": raw_text,
            }

        print(f"[CAMERA] Parsed result: {json.dumps(result, indent=2)}")
        station["camera"] = result
        log_event("CAMERA", f"Photo taken — {reason}" + (f" | prompt: {prompt}" if prompt else ""), data=result)
        return result
