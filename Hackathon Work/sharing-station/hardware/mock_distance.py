class MockDistance:
    def measure_distance(self) -> float:
        return float("inf")

    def is_close(self) -> bool:
        return False

    def cleanup(self):
        pass
