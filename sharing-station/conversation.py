import json
import os
import threading
import time
from collections import Counter

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    ClientTools,
    Conversation,
    ConversationInitiationData,
)
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface



class ConversationManager:
    def __init__(self):
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.conversation = None
        self.is_active = False
        self._state_lock = threading.Lock()
        self._active_user_id = None

        from services.hardware import camera, leds, servo
        from services.inventory import InventoryService
        from services.users import UserService

        self._camera = camera
        self._leds = leds
        self._servo = servo
        self._inventory = InventoryService()
        self._users = UserService()

    def _error_result(self, message: str):
        return json.dumps({"success": False, "error": message})

    def _tool_snap_camera_photo(self, params: dict):
        reason = params.get("reason") or params.get("context") or "agent requested camera context"
        prompt = params.get("prompt")
        return json.dumps(self._camera.capture_and_identify(reason, prompt))

    def _tool_get_inventory(self, params: dict):
        items = self._inventory.list_all()
        # Build a deduplicated summary so the LLM reliably reports ALL items.
        grouped = {}
        for item in items:
            name = item.get("name") or "Unknown"
            if name not in grouped:
                grouped[name] = {"name": name, "type": item.get("type", "unknown"), "copies": 0, "positions": []}
            grouped[name]["copies"] += 1
            if item.get("position"):
                grouped[name]["positions"].append(item["position"])
        summary_items = list(grouped.values())
        summary_text = ", ".join(
            f"{g['name']} ({g['copies']} available)" if g['copies'] > 1 else g['name']
            for g in summary_items
        ) or "nothing"
        return json.dumps({
            "summary": f"Available items: {summary_text}",
            "items": summary_items,
            "total_count": len(items),
        })

    def _tool_get_available_slots(self, params: dict):
        slots = self._inventory.get_available_slots()
        return json.dumps({"available_slots": slots, "total_available": len(slots)})

    def _tool_log_item(self, params: dict):
        item_name = params.get("item_name") or params.get("name")
        action = str(params.get("action") or "").strip().lower()
        user_id = params.get("user_id") or params.get("user") or self._active_user_id
        condition = params.get("condition")
        review = params.get("review")

        if not item_name:
            return self._error_result("item_name is required")
        if not user_id:
            return self._error_result("user_id is required")
        if action not in {"deposit", "retrieval"}:
            return self._error_result("action must be 'deposit' or 'retrieval'")

        if action == "deposit":
            slots_needed = params.get("slots_needed")
            if slots_needed is not None:
                slots_needed = int(slots_needed)
            item = self._inventory.add(item_name, user_id, condition, review, slots_needed=slots_needed)
            count = len(self._inventory.list_all())
            return json.dumps({"success": True, "item": item, "inventory_count": count})

        removed = self._inventory.remove(item_name, user_id)
        count = len(self._inventory.list_all())
        return json.dumps({"success": True, "item": removed, "inventory_count": count})

    def _tool_update_user_info(self, params: dict):
        user_id = params.get("user_id") or self._active_user_id
        if not user_id:
            return self._error_result("user_id is required")
        user = self._users.update(
            user_id,
            nickname=params.get("nickname"),
            memory=params.get("memory"),
            preferences=params.get("preferences"),
        )
        return json.dumps({"success": True, "user": user})

    def _tool_control_lights(self, params: dict):
        mode = params.get("mode") or "idle"
        position = params.get("position")
        if position is None:
            row = params.get("row")
            col = params.get("col")
            if row is not None and col is not None:
                position = [int(row), int(col)]
        slot_count = params.get("slot_count")
        if slot_count is not None:
            slot_count = int(slot_count)
        color = params.get("color")
        return json.dumps(self._leds.set_mode(mode, position, color, slot_count=slot_count))

    def _register_tool_aliases(self, client_tools: ClientTools, aliases: list[str], handler):
        for alias in aliases:
            client_tools.register(alias, handler)

    def _build_client_tools(self):
        client_tools = ClientTools()
        self._register_tool_aliases(
            client_tools,
            ["snap_camera_photo", "functions.snap_camera_photo", "camera", "functions.camera"],
            self._tool_snap_camera_photo,
        )
        self._register_tool_aliases(
            client_tools,
            ["get_inventory", "functions.get_inventory", "inventory", "functions.inventory"],
            self._tool_get_inventory,
        )
        self._register_tool_aliases(
            client_tools,
            ["get_available_slots", "functions.get_available_slots", "available_slots", "functions.available_slots"],
            self._tool_get_available_slots,
        )
        self._register_tool_aliases(
            client_tools,
            ["log_item", "functions.log_item", "log-item", "functions.log-item"],
            self._tool_log_item,
        )
        self._register_tool_aliases(
            client_tools,
            ["update_user_info", "functions.update_user_info", "user_info", "functions.user_info"],
            self._tool_update_user_info,
        )
        self._register_tool_aliases(
            client_tools,
            ["control_lights", "functions.control_lights", "lights", "functions.lights"],
            self._tool_control_lights,
        )
        return client_tools

    def _summarize_item_names(self, item_names: list) -> str:
        if not item_names:
            return "none"
        counts = Counter([name.strip() for name in item_names if name and name.strip()])
        if not counts:
            return "none"
        return ", ".join(
            f"{name} x{count}" if count > 1 else name
            for name, count in counts.items()
        )

    def _on_session_end(self):
        with self._state_lock:
            self.is_active = False
            self.conversation = None
            self._active_user_id = None
        print("[SESSION] Conversation ended — auto-locking in 10 seconds")
        threading.Thread(target=self._delayed_lock, daemon=True).start()

    def _delayed_lock(self, delay: float = 10.0):
        time.sleep(delay)
        # Only lock if no new session started in the meantime.
        if not self.is_active:
            self._servo.set_lock("lock")
            print("[SESSION] Door locked")

    def _send_initial_user_context(
        self,
        user_id: str = None,
        user_name: str = None,
        nickname: str = None,
        memories: list = None,
        contributed_items: list = None,
        checked_out_items: list = None,
        is_new_user: bool = False,
    ):
        convo = self.conversation
        if not convo:
            return

        parts = []
        if user_name:
            parts.append(f"Authenticated user name: {user_name}.")
        if nickname:
            parts.append(f"Nickname: {nickname}.")
        if user_id:
            parts.append(f"User ID: {user_id}.")
        parts.append(f"New user: {'yes' if is_new_user else 'no'}.")
        if memories:
            parts.append(f"Known memories/preferences: {'; '.join(memories)}.")
        if contributed_items is not None:
            if contributed_items:
                parts.append(
                    f"Items {user_name or 'this user'} has deposited and are currently in the station: "
                    f"{self._summarize_item_names(contributed_items)}."
                )
            else:
                parts.append(f"Items {user_name or 'this user'} has deposited and are currently in the station: none.")
        if checked_out_items is not None:
            if checked_out_items:
                parts.append(
                    f"Items {user_name or 'this user'} currently has checked out: "
                    f"{self._summarize_item_names(checked_out_items)}."
                )
            else:
                parts.append(f"Items {user_name or 'this user'} currently has checked out: none.")
        text = " ".join(parts).strip()
        if not text:
            return

        # Wait briefly for websocket readiness before sending the contextual update.
        for _ in range(20):
            try:
                convo.send_contextual_update(text)
                return
            except RuntimeError:
                time.sleep(0.1)
            except Exception as e:
                print(f"[SESSION] Failed to send contextual update: {e}")
                return

    def start(self, user_id: str = None, user_name: str = None,
              nickname: str = None, memories: list = None, contributed_items: list = None,
              checked_out_items: list = None, is_new_user: bool = False):
        """Start a new conversation session."""
        if self.is_active:
            self.stop()

        dynamic_vars = {}
        if user_id:
            dynamic_vars["user_id"] = user_id
        if user_name:
            dynamic_vars["user_name"] = user_name
            dynamic_vars["name"] = user_name
            dynamic_vars["display_name"] = user_name
        if nickname:
            dynamic_vars["nickname"] = nickname
        if memories:
            joined_memories = "; ".join(memories)
            dynamic_vars["memories"] = joined_memories
            dynamic_vars["memory_summary"] = joined_memories
        if contributed_items is not None:
            dynamic_vars["user_station_items"] = self._summarize_item_names(contributed_items)
        if checked_out_items is not None:
            dynamic_vars["user_checked_out_items"] = self._summarize_item_names(checked_out_items)
        dynamic_vars["is_new_user"] = "true" if is_new_user else "false"

        config = ConversationInitiationData(dynamic_variables=dynamic_vars)
        client_tools = self._build_client_tools()

        convo = Conversation(
            self.client,
            self.agent_id,
            user_id=user_id,
            config=config,
            client_tools=client_tools,
            requires_auth=bool(os.getenv("ELEVENLABS_API_KEY")),
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda r: print(f"[AGENT] {r}"),
            callback_agent_response_correction=lambda o, c: print(
                f"[AGENT CORRECTION] {o} -> {c}"
            ),
            callback_user_transcript=lambda t: print(f"[USER] {t}"),
            callback_end_session=self._on_session_end,
        )
        with self._state_lock:
            self.conversation = convo
            self.is_active = True
            self._active_user_id = user_id
        print(f"[SESSION] Starting conversation for user: {user_name or 'unknown'}")
        convo.start_session()

        threading.Thread(
            target=self._send_initial_user_context,
            kwargs={
                "user_id": user_id,
                "user_name": user_name,
                "nickname": nickname,
                "memories": memories,
                "contributed_items": contributed_items,
                "checked_out_items": checked_out_items,
                "is_new_user": is_new_user,
            },
            daemon=True,
        ).start()

    def stop(self):
        convo = self.conversation
        if not convo:
            return
        convo.end_session()
        convo.wait_for_session_end()
        with self._state_lock:
            self.is_active = False
            if self.conversation is convo:
                self.conversation = None

    def wait(self):
        convo = self.conversation
        if convo:
            convo.wait_for_session_end()


# Shared singleton — import this in main.py and routes/tools.py
manager = ConversationManager()
