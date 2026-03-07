import os

from supabase import Client, create_client

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_KEY")

supabase: Client | None = None

if _url and _key:
    supabase = create_client(_url, _key)
    print(f"[SUPABASE] Connected to {_url}")
else:
    print("[SUPABASE] SUPABASE_URL/KEY not set — user/auth flows disabled; inventory may use in-memory fallback")
