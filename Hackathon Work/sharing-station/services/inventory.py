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

    def add(self, name, user_id, condition=None, review=None, slot_row=None, slot_col=None, slots_needed=None):
        self._assert_supabase()
        return self._add_supabase(name, user_id, condition, review, slot_row, slot_col, slots_needed)

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

    def list_checked_out(self):
        """Returns all items currently checked out (borrowed), with borrower info."""
        self._assert_supabase()
        try:
            borrowed_result = (
                supabase.table("items")
                .select("*")
                .eq("status", "borrowed")
                .order("created_at", desc=False)
                .execute()
            )
            borrowed_rows = borrowed_result.data or []
        except Exception:
            return []

        if not borrowed_rows:
            return []

        # Find latest check_out transaction per item to identify the borrower
        tx_result = (
            supabase.table("transactions")
            .select("item_id,user_id,action,created_at")
            .order("created_at", desc=False)
            .execute()
        )
        latest_by_item = {}
        for tx in (tx_result.data or []):
            item_id = tx.get("item_id")
            if item_id and tx.get("action") == "check_out":
                latest_by_item[str(item_id)] = tx

        # Collect borrower user IDs and fetch their names
        borrower_ids = set()
        for item in borrowed_rows:
            tx = latest_by_item.get(str(item.get("id")))
            if tx and tx.get("user_id"):
                borrower_ids.add(str(tx["user_id"]))

        borrower_names = {}
        for uid in borrower_ids:
            user = self._users.get(uid)
            if user:
                borrower_names[uid] = user.get("name") or user.get("nickname") or "unknown"

        items = []
        for item in borrowed_rows:
            normalized = self._normalize(item)
            tx = latest_by_item.get(str(item.get("id")))
            if tx and tx.get("user_id"):
                uid = str(tx["user_id"])
                normalized["borrowed_by"] = borrower_names.get(uid, "unknown")
            else:
                normalized["borrowed_by"] = "unknown"
            items.append(normalized)
        return items

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

    def _get_occupied_slots(self):
        """Return a set of (row, col) tuples occupied by available items, accounting for multi-slot items."""
        self._assert_supabase()
        result = (
            supabase.table("items")
            .select("slot_row, slot_col, slot_count")
            .eq("status", "available")
            .not_.is_("slot_row", "null")
            .not_.is_("slot_col", "null")
            .execute()
        )
        occupied = set()
        for r in (result.data or []):
            row, col = r["slot_row"], r["slot_col"]
            count = r.get("slot_count") or 1
            for c in range(col, min(col + count, GRID_COLS)):
                occupied.add((row, c))
        return occupied

    def get_available_slots(self):
        """Return [row, col] positions not occupied by an available item."""
        occupied = self._get_occupied_slots()
        return [
            [row, col]
            for row in range(GRID_ROWS)
            for col in range(GRID_COLS)
            if (row, col) not in occupied
        ]

    def find_contiguous_slot(self, slots_needed: int = 1):
        """Find a starting [row, col] for a contiguous run of *slots_needed* columns,
        keeping at least 1 empty column of buffer between neighbouring items."""
        occupied = self._get_occupied_slots()

        for row in range(GRID_ROWS):
            for start_col in range(GRID_COLS - slots_needed + 1):
                # Check item columns + 1-col buffer on each side (clamped to grid edges)
                check_start = max(0, start_col - 1)
                check_end = min(GRID_COLS - 1, start_col + slots_needed)
                if not any((row, c) in occupied for c in range(check_start, check_end + 1)):
                    return [row, start_col]

        # Fallback: try without buffer if grid is crowded
        for row in range(GRID_ROWS):
            for start_col in range(GRID_COLS - slots_needed + 1):
                if not any((row, c) in occupied for c in range(start_col, start_col + slots_needed)):
                    return [row, start_col]

        return None

    # ── Supabase implementations ──────────────────────────────────────────────

    def _assert_supabase(self):
        if not supabase:
            raise RuntimeError(
                "Supabase is required for inventory operations. Set SUPABASE_URL and SUPABASE_KEY."
            )

    def _add_supabase(self, name, user_id, condition=None, review=None, slot_row=None, slot_col=None, slots_needed=None):
        resolved_user_id = self._resolve_user_id(user_id)
        count = max(1, int(slots_needed)) if slots_needed else 1
        data = {
            "name": name,
            "category": "unknown",
            "status": "available",
            "slot_count": count,
        }
        if resolved_user_id:
            data["donated_by"] = resolved_user_id

        # Use explicitly provided slot position if given, otherwise auto-assign
        if slot_row is not None and slot_col is not None:
            placement = [int(slot_row), int(slot_col)]
        else:
            placement = self.find_contiguous_slot(count)
        if placement is None:
            raise ValueError("No available contiguous slot run in the grid")
        data["slot_row"] = placement[0]
        data["slot_col"] = placement[1]

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
        slot_count = item.pop("slot_count", None) or 1
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
            "slot_count": slot_count,
        }
