from datetime import datetime

try:
    from database.client import supabase
except Exception:
    supabase = None

from services.users import UserService


class InventoryService:
    """Inventory store — Supabase if configured, otherwise in-memory with a 3×10 position grid."""

    def __init__(self):
        self._users = UserService()
        if not supabase:
            self._init_memory()

    def _init_memory(self):
        """Seed in-memory store. Items get positions in the 3-row × 10-col grid."""
        self._grid = [[None] * 10 for _ in range(3)]
        self.items = [
            {
                "id": "1",
                "name": "Settlers of Catan",
                "type": "board_game",
                "deposited_by": "peter",
                "deposited_at": "2025-03-06T10:00:00Z",
                "condition": "good, all pieces present",
                "review": "Great game, got tired of it after 20 plays though!",
                "position": [0, 0],
            },
            {
                "id": "2",
                "name": "The Great Gatsby",
                "type": "book",
                "deposited_by": "alice",
                "deposited_at": "2025-03-05T14:00:00Z",
                "condition": "slightly dog-eared",
                "review": None,
                "position": [0, 1],
            },
        ]
        self._grid[0][0] = "1"
        self._grid[0][1] = "2"
        self._next_id = 3

    # ── Slot helpers ─────────────────────────────────────────────────────────

    def _next_slot_memory(self):
        for r in range(3):
            for c in range(10):
                if self._grid[r][c] is None:
                    return [r, c]
        return None  # box is full

    # ── Public API ───────────────────────────────────────────────────────────

    def add(self, name, user_id, condition=None, review=None):
        if supabase:
            return self._add_supabase(name, user_id, condition, review)
        return self._add_memory(name, user_id, condition, review)

    def remove(self, name, user_id):
        if supabase:
            return self._remove_supabase(name, user_id)
        return self._remove_memory(name)

    def list_all(self):
        if supabase:
            try:
                result = (
                    supabase.table("items")
                    .select("*")
                    .eq("status", "available")
                    .order("created_at", desc=False)
                    .execute()
                )
                rows = result.data or []
            except Exception:
                # Fallback for older local schemas.
                result = supabase.table("items").select("*").execute()
                rows = result.data or []
            return [self._normalize(item, i) for i, item in enumerate(rows)]
        return self.items

    # ── In-memory implementations ─────────────────────────────────────────────

    def _add_memory(self, name, user_id, condition=None, review=None):
        position = self._next_slot_memory()
        item = {
            "id": str(self._next_id),
            "name": name,
            "type": "unknown",
            "deposited_by": user_id,
            "deposited_at": datetime.utcnow().isoformat() + "Z",
            "condition": condition,
            "review": review,
            "position": position,
        }
        self.items.append(item)
        if position:
            self._grid[position[0]][position[1]] = str(self._next_id)
        self._next_id += 1
        return item

    def _remove_memory(self, name):
        for item in self.items:
            if item["name"].lower() == name.lower():
                pos = item.get("position")
                if pos:
                    self._grid[pos[0]][pos[1]] = None
        self.items = [i for i in self.items if i["name"].lower() != name.lower()]

    # ── Supabase implementations ──────────────────────────────────────────────

    def _add_supabase(self, name, user_id, condition=None, review=None):
        resolved_user_id = self._resolve_user_id(user_id)
        data = {
            "name": name,
            "category": "unknown",
            "status": "available",
        }
        if resolved_user_id:
            data["donated_by"] = resolved_user_id

        result = supabase.table("items").insert(data).execute()
        inserted = result.data[0]
        self._insert_transaction(
            item=inserted,
            user_id=resolved_user_id,
            action="deposit",
        )

        for item in self.list_all():
            if str(item.get("id")) == str(inserted.get("id")):
                item["condition"] = condition
                item["review"] = review
                return item

        normalized = self._normalize(inserted)
        normalized["condition"] = condition
        normalized["review"] = review
        return normalized

    def _remove_supabase(self, name, user_id):
        resolved_user_id = self._resolve_user_id(user_id)
        result = (
            supabase.table("items")
            .select("*")
            .ilike("name", name)
            .eq("status", "available")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None

        item = result.data[0]
        try:
            supabase.table("items").update({"status": "borrowed"}).eq("id", item["id"]).execute()
        except Exception:
            # Older schema fallback: physically delete instead of status flip.
            supabase.table("items").delete().eq("id", item["id"]).execute()

        self._insert_transaction(item=item, user_id=resolved_user_id, action="retrieval")
        return self._normalize(item)

    def _resolve_user_id(self, user_id):
        if not user_id:
            return None
        user = self._users.get(user_id)
        if user:
            return user.get("id")
        user, _ = self._users.get_or_create_by_nfc(user_id)
        return user.get("id") if user else None

    def _insert_transaction(self, item, user_id, action: str):
        if not item or not user_id:
            return
        payloads = [
            {
                "user_id": user_id,
                "item_id": item.get("id"),
                "action": "check_in" if action == "deposit" else "check_out",
            },
            {
                "item_name": item.get("name"),
                "user_id": user_id,
                "action": action,
            },
        ]
        for payload in payloads:
            try:
                supabase.table("transactions").insert(payload).execute()
                return
            except Exception:
                continue

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _normalize(self, item: dict, synthetic_index: int | None = None) -> dict:
        """Map DB row shape to the API/UI item format."""
        item = dict(item)

        row = item.pop("position_row", None)
        col = item.pop("position_col", None)
        if row is not None and col is not None:
            position = [row, col]
        elif synthetic_index is not None and synthetic_index < 30:
            position = [synthetic_index // 10, synthetic_index % 10]
        else:
            position = None

        return {
            "id": str(item.get("id")),
            "name": item.get("name"),
            "type": item.get("type") or item.get("category") or "unknown",
            "deposited_by": item.get("deposited_by") or item.get("donated_by"),
            "deposited_at": item.get("deposited_at") or item.get("created_at"),
            "condition": item.get("condition"),
            "review": item.get("review"),
            "status": item.get("status", "available"),
            "position": position,
        }
