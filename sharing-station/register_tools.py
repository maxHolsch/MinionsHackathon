"""
Register client tools on the ElevenLabs agent.

Run once: python register_tools.py

Tools are created at the workspace level (/v1/convai/tools) and then
linked to the agent via tool_ids.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
BASE = "https://api.elevenlabs.io/v1/convai"
HEADERS = {"xi-api-key": API_KEY, "Content-Type": "application/json"}

# ── tool definitions ────────────────────────────────────────────────
# Each entry is the tool_config body for POST /v1/convai/tools.
TOOL_CONFIGS = [
    {
        "type": "client",
        "name": "snap_camera_photo",
        "description": (
            "Take a photo with the station camera and analyze it with AI vision. "
            "Use this when a user deposits or retrieves an item to identify it, "
            "assess its size for slot placement, or verify the station contents. "
            "You can pass a custom prompt to ask the vision system specific questions "
            "(e.g. item size, condition, what's in a particular area). "
            "Returns detected items with names, types, conditions, and size estimates."
        ),
        "response_timeout_secs": 30,
        "expects_response": True,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the photo is being taken, e.g. 'user depositing an item' or 'confirming retrieval'",
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "Optional custom question for the vision system. "
                        "Use this to ask specific things like 'How large is this item? "
                        "Would it fit in a single slot or does it need multiple?' or "
                        "'Describe the condition of this item in detail'. "
                        "If omitted, the default item identification prompt is used."
                    ),
                },
            },
            "required": ["reason"],
        },
    },
    {
        "type": "client",
        "name": "get_inventory",
        "description": (
            "Retrieve the full list of items currently available in the sharing station. "
            "Use this when the user asks what's available, or when you need to know "
            "the current inventory before logging an item in or out."
        ),
        "response_timeout_secs": 10,
        "expects_response": True,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "client",
        "name": "get_available_slots",
        "description": (
            "Get a list of available physical slot positions in the 3-row by 10-column "
            "storage grid. Each slot is identified by [row, col]. Use this BEFORE depositing "
            "an item so you can pick a slot, light it up, and tell the user where to place it. "
            "Prefer filling left-to-right, top-to-bottom (pick the first available slot)."
        ),
        "response_timeout_secs": 10,
        "expects_response": True,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "client",
        "name": "log_item",
        "description": (
            "Log an item being deposited into or retrieved from the station. "
            "Call this AFTER confirming the item identity with the user. "
            "action must be 'deposit' or 'retrieval'. "
            "For deposits, include slots_needed (from the camera's estimated size) so "
            "the system can find a contiguous block of slots with spacing between items. "
            "The system auto-assigns the best available position by default. "
            "Only pass slot_row and slot_col if the user specifically requests a custom location."
        ),
        "response_timeout_secs": 10,
        "expects_response": True,
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Name of the item being logged"},
                "action": {
                    "type": "string",
                    "description": "Either 'deposit' or 'retrieval'",
                    "enum": ["deposit", "retrieval"],
                },
                "user_id": {"type": "string", "description": "ID of the user performing the action"},
                "condition": {"type": "string", "description": "Condition of the item (for deposits)"},
                "review": {"type": "string", "description": "Short user review or comment about the item"},
                "slots_needed": {
                    "type": "integer",
                    "description": (
                        "How many contiguous grid columns the item needs (from the camera's slots_needed estimate). "
                        "Rough guide: small accessory=1, paperback=2, hardcover book=3, board game=6-8. "
                        "Defaults to 1 if omitted."
                    ),
                },
                "slot_row": {
                    "type": "integer",
                    "description": "Row of the custom slot position. Only use when the user asks to place the item at a specific location.",
                },
                "slot_col": {
                    "type": "integer",
                    "description": "Column of the custom slot position. Only use when the user asks to place the item at a specific location.",
                },
            },
            "required": ["item_name", "action", "user_id"],
        },
    },
    {
        "type": "client",
        "name": "update_user_info",
        "description": (
            "Save user preferences, nicknames, or memories for future visits. "
            "Use this to remember things the user tells you about themselves."
        ),
        "response_timeout_secs": 10,
        "expects_response": True,
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "ID of the user"},
                "nickname": {"type": "string", "description": "A nickname for the user"},
                "memory": {"type": "string", "description": "Something to remember about the user"},
                "preferences": {"type": "string", "description": "User preferences to store"},
            },
            "required": ["user_id"],
        },
    },
    {
        "type": "client",
        "name": "control_lights",
        "description": (
            "Control the LED lights on the station to highlight item positions. "
            "Use mode 'highlight' with a position to show where an item is, "
            "or 'idle' to return to default. "
            "For multi-slot items, set slot_count to highlight a contiguous range of columns."
        ),
        "response_timeout_secs": 5,
        "expects_response": True,
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "description": "Light mode: 'idle', 'highlight', 'success', 'error'"},
                "row": {"type": "integer", "description": "Row position (0-2) of the item to highlight"},
                "col": {"type": "integer", "description": "Starting column position (0-9) of the item to highlight"},
                "slot_count": {"type": "integer", "description": "Number of contiguous columns to highlight (default 1)"},
                "color": {"type": "string", "description": "Color for the lights (e.g. 'green', 'red', 'blue')"},
            },
            "required": ["mode"],
        },
    },
]


def list_workspace_tools():
    """Get all existing workspace-level tools."""
    resp = requests.get(f"{BASE}/tools", headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("tools", [])


def delete_workspace_tool(tool_id):
    """Delete a workspace-level tool."""
    resp = requests.delete(f"{BASE}/tools/{tool_id}", headers=HEADERS)
    resp.raise_for_status()


def create_workspace_tool(tool_config):
    """Create a workspace-level tool, returns the tool ID."""
    resp = requests.post(f"{BASE}/tools", headers=HEADERS, json={"tool_config": tool_config})
    resp.raise_for_status()
    return resp.json()["id"]


def update_agent_tool_ids(tool_ids):
    """Link workspace tools to the agent via tool_ids."""
    resp = requests.patch(
        f"{BASE}/agents/{AGENT_ID}",
        headers=HEADERS,
        json={
            "conversation_config": {
                "agent": {
                    "prompt": {
                        "tool_ids": tool_ids,
                    },
                },
            },
        },
    )
    resp.raise_for_status()
    return resp.json()


# ── main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Step 1: Check existing workspace tools.
    existing = list_workspace_tools()
    existing_by_name = {
        t.get("tool_config", {}).get("name"): t["id"]
        for t in existing
    }
    if existing:
        print(f"Found {len(existing)} existing workspace tools: {list(existing_by_name.keys())}")

    # Step 2: Create each tool at the workspace level (skip if already exists by name).
    print(f"\nCreating {len(TOOL_CONFIGS)} tools...")
    new_tool_ids = []
    for config in TOOL_CONFIGS:
        name = config["name"]
        if name in existing_by_name:
            # Reuse existing tool ID
            tool_id = existing_by_name[name]
            print(f"  ↺ {name} → {tool_id} (already exists)")
        else:
            tool_id = create_workspace_tool(config)
            print(f"  ✓ {name} → {tool_id} (created)")
        new_tool_ids.append(tool_id)

    # Step 3: Link all tools to the agent.
    print(f"\nLinking {len(new_tool_ids)} tools to agent {AGENT_ID}...")
    result = update_agent_tool_ids(new_tool_ids)
    linked = result.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    print(f"Agent now has {len(linked)} tool_ids")

    print("\nDone! Tools are registered and linked to the agent.")
