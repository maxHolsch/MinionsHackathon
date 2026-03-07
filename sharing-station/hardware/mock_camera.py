class MockCamera:
    """Mock camera that returns fake item identifications."""

    def capture_and_identify(self, reason: str) -> dict:
        print(f"[MOCK CAMERA] Capturing photo — reason: {reason}")
        return {
            "items_detected": [
                {
                    "name": "Dune by Frank Herbert",
                    "type": "book",
                    "condition": "good",
                }
            ],
            "raw_description": "A paperback copy of Dune by Frank Herbert, slightly worn spine",
        }
