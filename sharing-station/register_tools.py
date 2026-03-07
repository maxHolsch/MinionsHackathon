"""
Register client tools on the ElevenLabs agent.

Run once: python register_tools.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from elevenlabs.client import ElevenLabs
from elevenlabs.types import (
    ConversationalConfig,
    AgentConfig,
    PromptAgentApiModelInput,
    PromptAgentApiModelInputToolsItem_Client,
    ObjectJsonSchemaPropertyInput,
    LiteralJsonSchemaProperty,
)

API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")

client = ElevenLabs(api_key=API_KEY)

# ── tool definitions ────────────────────────────────────────────────
tools = [
    PromptAgentApiModelInputToolsItem_Client(
        name="snap_camera_photo",
        description=(
            "Take a photo with the station camera to see what items are physically "
            "present in the box. Use this when a user deposits or retrieves an item "
            "so you can visually confirm what it is. Returns a list of detected items "
            "and a text description."
        ),
        response_timeout_secs=30,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "reason": LiteralJsonSchemaProperty(
                    type="string",
                    description="Why the photo is being taken, e.g. 'user depositing an item' or 'confirming retrieval'",
                ),
            },
            required=["reason"],
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="get_inventory",
        description=(
            "Retrieve the full list of items currently available in the sharing station. "
            "Use this when the user asks what's available, or when you need to know "
            "the current inventory before logging an item in or out."
        ),
        response_timeout_secs=10,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={},
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="get_available_slots",
        description=(
            "Get a list of available physical slot positions in the 3-row by 10-column "
            "storage grid. Each slot is identified by [row, col]. Use this BEFORE depositing "
            "an item so you can pick a slot, light it up, and tell the user where to place it. "
            "Prefer filling left-to-right, top-to-bottom (pick the first available slot)."
        ),
        response_timeout_secs=10,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={},
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="log_item",
        description=(
            "Log an item being deposited into or retrieved from the station. "
            "Call this AFTER confirming the item identity with the user. "
            "action must be 'deposit' or 'retrieval'. "
            "For deposits, include slot_row and slot_col to record which physical "
            "slot the item was placed in (from get_available_slots)."
        ),
        response_timeout_secs=10,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "item_name": LiteralJsonSchemaProperty(
                    type="string",
                    description="Name of the item being logged",
                ),
                "action": LiteralJsonSchemaProperty(
                    type="string",
                    description="Either 'deposit' or 'retrieval'",
                    enum=["deposit", "retrieval"],
                ),
                "user_id": LiteralJsonSchemaProperty(
                    type="string",
                    description="ID of the user performing the action",
                ),
                "condition": LiteralJsonSchemaProperty(
                    type="string",
                    description="Condition of the item (for deposits)",
                ),
                "review": LiteralJsonSchemaProperty(
                    type="string",
                    description="Short user review or comment about the item",
                ),
                "slot_row": LiteralJsonSchemaProperty(
                    type="integer",
                    description="Row (0-2) of the physical slot where the item is placed (for deposits)",
                ),
                "slot_col": LiteralJsonSchemaProperty(
                    type="integer",
                    description="Column (0-9) of the physical slot where the item is placed (for deposits)",
                ),
            },
            required=["item_name", "action", "user_id"],
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="update_user_info",
        description=(
            "Save user preferences, nicknames, or memories for future visits. "
            "Use this to remember things the user tells you about themselves."
        ),
        response_timeout_secs=10,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "user_id": LiteralJsonSchemaProperty(
                    type="string",
                    description="ID of the user",
                ),
                "nickname": LiteralJsonSchemaProperty(
                    type="string",
                    description="A nickname for the user",
                ),
                "memory": LiteralJsonSchemaProperty(
                    type="string",
                    description="Something to remember about the user",
                ),
                "preferences": LiteralJsonSchemaProperty(
                    type="string",
                    description="User preferences to store",
                ),
            },
            required=["user_id"],
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="control_lights",
        description=(
            "Control the LED lights on the station to highlight item positions. "
            "Use mode 'highlight' with a position to show where an item is, "
            "or 'idle' to return to default."
        ),
        response_timeout_secs=5,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "mode": LiteralJsonSchemaProperty(
                    type="string",
                    description="Light mode: 'idle', 'highlight', 'success', 'error'",
                ),
                "row": LiteralJsonSchemaProperty(
                    type="integer",
                    description="Row position of the item to highlight",
                ),
                "col": LiteralJsonSchemaProperty(
                    type="integer",
                    description="Column position of the item to highlight",
                ),
                "color": LiteralJsonSchemaProperty(
                    type="string",
                    description="Color for the lights (e.g. 'green', 'red', 'blue')",
                ),
            },
            required=["mode"],
        ),
    ),
    PromptAgentApiModelInputToolsItem_Client(
        name="control_lock",
        description=(
            "Control the physical door lock on the station. "
            "Use 'unlock' to open the door, 'lock' to close it. "
            "Locking also ends the conversation session."
        ),
        response_timeout_secs=5,
        parameters=ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "action": LiteralJsonSchemaProperty(
                    type="string",
                    description="Either 'lock' or 'unlock'",
                    enum=["lock", "unlock"],
                ),
            },
            required=["action"],
        ),
    ),
]

# ── fetch current config and update with tools ──────────────────────
agent = client.conversational_ai.agents.get(AGENT_ID)
current_prompt = agent.conversation_config.agent.prompt

print(f"Agent: {agent.name}")
print(f"Current tools count: {len(current_prompt.tools or [])}")
print(f"Adding {len(tools)} client tools...")

updated = client.conversational_ai.agents.update(
    agent_id=AGENT_ID,
    conversation_config={
        "agent": {
            "prompt": {
                "prompt": current_prompt.prompt,
                "llm": current_prompt.llm,
                "temperature": current_prompt.temperature,
                "tools": [t.model_dump(exclude_none=True) for t in tools],
            },
        },
    },
)

new_tools = updated.conversation_config.agent.prompt.tools or []
print(f"Updated tools count: {len(new_tools)}")
for t in new_tools:
    print(f"  ✓ {getattr(t, 'name', '?')} ({getattr(t, 'type', '?')})")
print("\nDone! Tools are now registered on the agent.")
