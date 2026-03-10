from station_state import station, log_event


class MockCamera:
    """Mock camera that returns fake item identifications."""

    def capture_and_identify(self, reason: str, prompt: str = None) -> dict:
        result = {
            "items_detected": [
                {"name": "Dune by Frank Herbert", "type": "book", "condition": "good", "estimated_size": "medium"}
            ],
            "raw_description": "A paperback copy of Dune by Frank Herbert, slightly worn spine. Medium-sized paperback.",
        }
        station["camera"] = result
        log_event("CAMERA", f"Photo taken — {reason}" + (f" | prompt: {prompt}" if prompt else ""), data=result)
        return result
