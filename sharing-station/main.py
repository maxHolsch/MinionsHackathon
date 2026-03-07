from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from routes.tools import router as tools_router
from routes.auth import router as auth_router
from routes.status import router as status_router
from conversation import manager as conversation_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[SERVER] Sharing Station server starting...")
    yield
    # Shutdown
    print("[SERVER] Shutting down...")
    conversation_manager.stop()


app = FastAPI(title="Sharing Station", lifespan=lifespan)
app.include_router(tools_router, prefix="/api/tools")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(status_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "conversation_active": conversation_manager.is_active}


@app.post("/conversation/start")
async def start_conversation(user_name: str = "Unknown", user_id: str = None,
                              nickname: str = None, is_new_user: bool = False):
    """Start a conversation session (for testing via API — NFC auth auto-starts in production)."""
    from services.users import UserService
    users = UserService()
    try:
        user = users.get(user_id) if user_id else None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    memories = user.get("memories") or [] if user else []
    nickname = nickname or (user.get("nickname") if user else None)
    conversation_manager.start(user_name=user_name, user_id=user_id,
                                nickname=nickname, memories=memories, is_new_user=is_new_user)
    return {"status": "started", "user": user_name, "is_new_user": is_new_user}


@app.post("/conversation/stop")
async def stop_conversation():
    """Stop the current conversation session."""
    conversation_manager.stop()
    return {"status": "stopped"}


# Static files mount LAST — it's a catch-all on "/"
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
