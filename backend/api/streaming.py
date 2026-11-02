"""
Формат потока (Server-Sent Events):
    event: status   data: {"text": "Ищу отели…"}       — сколько угодно раз
    event: reply    data: {...тот же JSON, что у /api/chat...}
    event: error    data: {"text": "..."}               — только если всё совсем плохо
    event: done     data: {}                            — поток закончен
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Optional

from agent.core import load_state, run_agent

AGENT_TIMEOUT = 150        # секунд на весь ход агента (несколько вызовов модели)
PING_EVERY = 15            # пустое событие, чтобы прокси/браузер не рвали соединение

log = logging.getLogger("chat")


def fallback_reply(session_id: str, text: str) -> dict:
    """Ответ «что-то пошло не так», но в формате ChatResponse — фронт не ломается."""
    state = load_state(session_id)
    return {"reply": {"text": text, "cards": [], "quick_replies": []},
            "trip": state.public_view()}


async def safe_run(session_id: str, message: Optional[str], action: Optional[dict],
                   emit=None) -> dict:
    """run_agent с таймаутом и перехватом любых ошибок."""
    if not (message and message.strip()) and not action:
        return fallback_reply(session_id, "Напишите, куда и когда хотите поехать — я подберу варианты.")
    try:
        return await asyncio.wait_for(
            run_agent(session_id, user_text=message, action=action, emit=emit), AGENT_TIMEOUT)
    except asyncio.TimeoutError:
        log.warning("agent timeout, session=%s", session_id)
        return fallback_reply(session_id, "Подбор занял слишком много времени. Отправьте сообщение ещё "
                                          "раз — всё, что вы уже выбрали, сохранено.")
    except Exception:
        log.exception("agent failed, session=%s", session_id)
        return fallback_reply(session_id, "Что-то пошло не так на нашей стороне. "
                                          "Попробуйте отправить сообщение ещё раз.")


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def stream_events(session_id: str, message: Optional[str], action: Optional[dict]) -> AsyncIterator[str]:
    """Генератор строк SSE: статусы по ходу работы агента, потом ответ."""
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: str, data: dict):
        await queue.put((event, data))

    async def worker():
        try:
            result = await safe_run(session_id, message, action, emit=emit)
            await queue.put(("reply", result))
        except Exception as e:                       # safe_run уже ловит всё, это на всякий случай
            await queue.put(("error", {"text": str(e)}))
        finally:
            await queue.put(None)                    # сигнал «конец»

    task = asyncio.create_task(worker())
    try:
        yield sse("status", {"text": "Думаю…"})
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), PING_EVERY)
            except asyncio.TimeoutError:
                yield ": ping\n\n"                   # комментарий SSE — держит соединение живым
                continue
            if item is None:
                break
            yield sse(*item)
        yield sse("done", {})
    finally:
        if not task.done():                          # пользователь закрыл вкладку — останавливаем агента
            task.cancel()