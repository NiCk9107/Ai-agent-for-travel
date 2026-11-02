import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.state import TripState
from api.schemas import ChatRequest, ChatResponse, SessionResponse
from api.streaming import safe_run, stream_events
from db.database import save_state

router = APIRouter()


@router.post("/session", response_model=SessionResponse)
def create_session():
    session_id = "s_" + uuid.uuid4().hex[:8]
    save_state(TripState(session_id=session_id))
    return SessionResponse(session_id=session_id)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Обычный запрос: ждём весь ответ агента. Ошибки и таймауты — вежливым текстом."""
    return await safe_run(req.session_id, req.message,
                          req.action.model_dump() if req.action else None)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """То же, но со статусами по ходу работы (SSE): «Ищу отели…», «Проверяю состыковки…»."""
    return StreamingResponse(
        stream_events(req.session_id, req.message, req.action.model_dump() if req.action else None),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )