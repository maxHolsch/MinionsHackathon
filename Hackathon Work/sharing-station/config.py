import os
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Runtime mode for voice transport:
# - "webrtc": browser handles mic/speaker via ElevenLabs JS SDK (recommended)
# - "python": server handles mic/speaker via Python SDK + PyAudio
VOICE_RUNTIME = (os.getenv("VOICE_RUNTIME") or "webrtc").strip().lower()
if VOICE_RUNTIME not in {"webrtc", "python"}:
    VOICE_RUNTIME = "webrtc"

PI_IP = os.getenv("PI_IP")
