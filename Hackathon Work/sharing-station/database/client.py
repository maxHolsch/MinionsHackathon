import os

from supabase import Client, create_client
from dotenv import load_dotenv

# Ensure env vars are available even when this module is imported outside main.py.
load_dotenv()

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_KEY")

supabase: Client | None = None

if _url and _key:
    supabase = create_client(_url, _key)
    print(f"[SUPABASE] Connected to {_url}")
else:
    print("[SUPABASE] SUPABASE_URL/KEY not set — auth/user/inventory flows disabled")
