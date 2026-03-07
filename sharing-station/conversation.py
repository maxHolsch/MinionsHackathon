import os

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
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

    def start(self, user_id: str = None, user_name: str = None, is_new_user: bool = False):
        """Start a new conversation session."""
        dynamic_vars = {}
        if user_name:
            dynamic_vars["user_name"] = user_name
        if is_new_user:
            dynamic_vars["is_new_user"] = "true"

        config = ConversationInitiationData(dynamic_variables=dynamic_vars)

        self.conversation = Conversation(
            self.client,
            self.agent_id,
            config=config,
            requires_auth=bool(os.getenv("ELEVENLABS_API_KEY")),
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda r: print(f"[AGENT] {r}"),
            callback_agent_response_correction=lambda o, c: print(
                f"[AGENT CORRECTION] {o} -> {c}"
            ),
            callback_user_transcript=lambda t: print(f"[USER] {t}"),
        )
        self.conversation.start_session()
        self.is_active = True
        print(f"[SESSION] Conversation started for user: {user_name or 'unknown'}")

    def stop(self):
        if self.conversation:
            self.conversation.end_session()
            self.conversation.wait_for_session_end()
            self.is_active = False
            print("[SESSION] Conversation ended")

    def wait(self):
        if self.conversation:
            self.conversation.wait_for_session_end()


# Shared singleton — import this in main.py and routes/tools.py
manager = ConversationManager()
