from station_state import station, log_event


class MockCamera:
    """Mock camera that returns fake item identifications."""

    def capture_and_identify(self, reason: str) -> dict:
        result = {
            "items_detected": [
                {"name": "Dune by Frank Herbert", "type": "book", "condition": "good"}
            ],
            "raw_description": "A paperback copy of Dune by Frank Herbert, slightly worn spine",
        }
        station["camera"] = result
        log_event("CAMERA", f"Photo taken — {reason}", data=result)
        return result
