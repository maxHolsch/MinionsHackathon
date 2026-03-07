from datetime import datetime


class InventoryService:
    """In-memory inventory. Swap for Supabase later."""

    def __init__(self):
        # Pre-seed with some items for testing
        self.items = [
            {
                "id": "1",
                "name": "Settlers of Catan",
                "type": "board_game",
                "deposited_by": "peter",
                "deposited_at": "2025-03-06T10:00:00Z",
                "condition": "good, all pieces present",
                "review": "Great game, got tired of it after 20 plays though!",
            },
            {
                "id": "2",
                "name": "The Great Gatsby",
                "type": "book",
                "deposited_by": "alice",
                "deposited_at": "2025-03-05T14:00:00Z",
                "condition": "slightly dog-eared",
                "review": None,
            },
        ]
        self._next_id = 3

    def add(self, name, user_id, condition=None, review=None):
        item = {
            "id": str(self._next_id),
            "name": name,
            "type": "unknown",
            "deposited_by": user_id,
            "deposited_at": datetime.utcnow().isoformat() + "Z",
            "condition": condition,
            "review": review,
        }
        self.items.append(item)
        self._next_id += 1
        return item

    def remove(self, name, user_id):
        self.items = [i for i in self.items if i["name"].lower() != name.lower()]

    def list_all(self):
        return self.items
