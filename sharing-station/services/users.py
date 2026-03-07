try:
    from database.client import supabase
except Exception:
    supabase = None

PREFERENCES_PREFIX = "preferences::"


class UserService:
    """User store backed by Supabase."""

    # ── Public API ───────────────────────────────────────────────────────────

    def get_or_create_by_nfc(self, nfc_id: str):
        """Return (user, is_new_user) for an NFC tag."""
        self._assert_supabase()
        user_row = self._fetch_user_by_nfc(nfc_id)
        is_new_user = user_row is None
        if is_new_user:
            user_row = self._create_supabase_user(nfc_id=nfc_id, name="neighbor")
        if not user_row:
            raise RuntimeError(f"Failed to load or create user for NFC tag '{nfc_id}'")
        self._set_active_user(user_row["id"])
        return self._normalize_supabase_user(user_row), is_new_user

    def get_by_nfc(self, nfc_id: str):
        """Return user by NFC tag ID, or None if not a known user."""
        self._assert_supabase()
        user_row = self._fetch_user_by_nfc(nfc_id)
        return self._normalize_supabase_user(user_row) if user_row else None

    def get(self, user_id: str):
        """Return user by ID, or None."""
        self._assert_supabase()
        user_row = self._fetch_user_by_id(user_id) or self._fetch_user_by_nfc(user_id)
        return self._normalize_supabase_user(user_row) if user_row else None

    def update(self, user_id, nickname=None, memory=None, preferences=None):
        self._assert_supabase()
        user_row = self._fetch_user_by_id(user_id) or self._fetch_user_by_nfc(user_id)
        if not user_row:
            user_row = self._create_supabase_user(nfc_id=user_id, name="neighbor")
        if not user_row:
            raise RuntimeError(f"Failed to resolve user '{user_id}'")

        resolved_id = user_row["id"]
        data = {}
        if nickname:
            data["nickname"] = nickname

        if data:
            supabase.table("users").update(data).eq("id", resolved_id).execute()

        if memory:
            self._insert_memory(resolved_id, memory)

        if preferences:
            self._insert_memory(resolved_id, f"{PREFERENCES_PREFIX}{preferences}")

        return self.get(str(resolved_id))

    # ── Supabase helpers ──────────────────────────────────────────────────────

    def _assert_supabase(self):
        if not supabase:
            raise RuntimeError("Supabase is required for user operations. Set SUPABASE_URL and SUPABASE_KEY.")

    def _fetch_user_by_id(self, user_id: str):
        result = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
        return result.data[0] if result.data else None

    def _fetch_user_by_nfc(self, nfc_id: str):
        for column in ("nfc_uuid", "nfc_id"):
            try:
                result = (
                    supabase.table("users")
                    .select("*")
                    .eq(column, nfc_id)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception:
                continue
        return None

    def _create_supabase_user(self, nfc_id: str, name: str):
        payloads = [
            {"nfc_uuid": nfc_id, "name": name},
            {"nfc_id": nfc_id, "name": name},
            {"id": nfc_id, "nfc_id": nfc_id, "name": name},
        ]
        for payload in payloads:
            try:
                result = supabase.table("users").insert(payload).select("*").execute()
                if result.data:
                    return result.data[0]
            except Exception:
                continue
        return None

    def _set_active_user(self, user_id):
        try:
            supabase.table("users").update({"is_active": False}).eq("is_active", True).execute()
            supabase.table("users").update({"is_active": True}).eq("id", user_id).execute()
        except Exception:
            # Some DB snapshots may not include `is_active`; ignore in that case.
            pass

    def _insert_memory(self, user_id, content: str):
        supabase.table("memories").insert({"user_id": user_id, "content": content}).execute()

    def _normalize_supabase_user(self, user_row: dict):
        memory_rows = self._fetch_memory_rows(user_row["id"])
        memories = []
        preferences = None

        for row in memory_rows:
            content = row.get("content")
            if not content:
                continue
            if content.startswith(PREFERENCES_PREFIX):
                preferences = content[len(PREFERENCES_PREFIX):].strip() or preferences
            else:
                memories.append(content)

        return {
            "id": str(user_row.get("id")),
            "nfc_id": user_row.get("nfc_uuid") or user_row.get("nfc_id"),
            "name": user_row.get("name"),
            "nickname": user_row.get("nickname"),
            "memories": memories,
            "preferences": preferences,
            "is_active": user_row.get("is_active"),
        }

    def _fetch_memory_rows(self, user_id):
        result = (
            supabase.table("memories")
            .select("content,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        return result.data or []
