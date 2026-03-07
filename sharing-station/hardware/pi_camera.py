import base64
import json

from anthropic import Anthropic


class PiCamera:
    """Real Pi camera with Anthropic vision for item identification."""

    def __init__(self):
        # Lazy import — only works on Raspberry Pi
        from picamera2 import Picamera2

        self.cam = Picamera2()
        self.cam.configure(self.cam.create_still_configuration())
        self.anthropic = Anthropic()

    def capture_and_identify(self, reason: str) -> dict:
        self.cam.start()
        self.cam.capture_file("/tmp/station_photo.jpg")
        self.cam.stop()

        with open("/tmp/station_photo.jpg", "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
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
                            "text": (
                                "You are the vision system for a community sharing station. "
                                "Identify any items (books, board games, objects) visible in this image. "
                                f"Context: {reason}. "
                                'Return JSON: {"items_detected": [{"name": "...", "type": "book|board_game|other", "condition": "..."}], "raw_description": "..."}'
                            ),
                        },
                    ],
                }
            ],
        )

        try:
            return json.loads(response.content[0].text)
        except (json.JSONDecodeError, IndexError):
            return {
                "items_detected": [],
                "raw_description": response.content[0].text,
            }
