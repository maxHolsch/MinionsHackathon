try:
    from database.client import supabase
except Exception:
    supabase = None

from services.users import UserService


GRID_ROWS = 3
GRID_COLS = 10


class InventoryService:
    """Inventory store backed by Supabase."""

    def __init__(self):
        self._users = UserService()

    # ── Public API ───────────────────────────────────────────────────────────

    def add(self, name, user_id, condition=None, review=None, slot_row=None, slot_col=None):
        self._assert_supabase()
        return self._add_supabase(name, user_id, condition, review, slot_row, slot_col)

    def remove(self, name, user_id):
        self._assert_supabase()
        return self._remove_supabase(name, user_id)

    def list_all(self):
        self._assert_supabase()
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

    def list_user_contributions(self, user_id):
        """Items currently available in the station that this user deposited."""
        self._assert_supabase()
        resolved_user_id = self._resolve_user_id(user_id)
        if not resolved_user_id:
            return []
        return [
            item for item in self.list_all()
            if str(item.get("deposited_by")) == str(resolved_user_id)
        ]

    def list_user_checked_out(self, user_id):
        """Items this user currently has checked out from the station."""
        self._assert_supabase()
        resolved_user_id = self._resolve_user_id(user_id)
        if not resolved_user_id:
            return []

        tx_result = (
            supabase.table("transactions")
            .select("item_id,user_id,action,created_at")
            .order("created_at", desc=False)
            .execute()
        )
        tx_rows = tx_result.data or []
        latest_by_item = {}
        for tx in tx_rows:
            item_id = tx.get("item_id")
            if item_id:
                latest_by_item[str(item_id)] = tx

        borrowed_result = (
            supabase.table("items")
            .select("*")
            .eq("status", "borrowed")
            .order("created_at", desc=False)
            .execute()
        )
        borrowed_rows = borrowed_result.data or []

        checked_out = []
        for item in borrowed_rows:
            item_id = str(item.get("id"))
            latest_tx = latest_by_item.get(item_id)
            if not latest_tx:
                continue
            if (
                str(latest_tx.get("user_id")) == str(resolved_user_id)
                and latest_tx.get("action") == "check_out"
            ):
                checked_out.append(self._normalize(item))

        return checked_out

    def get_available_slots(self):
        """Return [row, col] positions not occupied by an available item."""
        self._assert_supabase()
        result = (
            supabase.table("items")
            .select("slot_row, slot_col")
            .eq("status", "available")
            .not_.is_("slot_row", "null")
            .not_.is_("slot_col", "null")
            .execute()
        )
        occupied = {(r["slot_row"], r["slot_col"]) for r in (result.data or [])}
        return [
            [row, col]
            for row in range(GRID_ROWS)
            for col in range(GRID_COLS)
            if (row, col) not in occupied
        ]

    # ── Supabase implementations ──────────────────────────────────────────────

    def _assert_supabase(self):
        if not supabase:
            raise RuntimeError(
                "Supabase is required for inventory operations. Set SUPABASE_URL and SUPABASE_KEY."
            )

    def _add_supabase(self, name, user_id, condition=None, review=None, slot_row=None, slot_col=None):
        resolved_user_id = self._resolve_user_id(user_id)
        data = {
            "name": name,
            "category": "unknown",
            "status": "available",
        }
        if resolved_user_id:
            data["donated_by"] = resolved_user_id
        if slot_row is not None and slot_col is not None:
            if not (0 <= slot_row < GRID_ROWS and 0 <= slot_col < GRID_COLS):
                raise ValueError(f"Slot [{slot_row}, {slot_col}] is outside the {GRID_ROWS}x{GRID_COLS} grid")
            data["slot_row"] = slot_row
            data["slot_col"] = slot_col

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

        row = item.pop("slot_row", None)
        if row is None:
            row = item.pop("position_row", None)
        col = item.pop("slot_col", None)
        if col is None:
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
