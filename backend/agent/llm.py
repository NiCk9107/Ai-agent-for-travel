"""
Обёртка над LLM. Модель меняется одной строкой в .env (LLM_MODEL).
Работает с любым OpenAI-совместимым API: OpenRouter, OpenAI, Gemini и др.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import (APIConnectionError, APITimeoutError, AsyncOpenAI,
                    InternalServerError, RateLimitError)

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")          # дешёвая для разработки
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")           # запасная (на день 5)

_client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY or "missing", timeout=60)


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)   # подпись Gemini (thought_signature) и т.п.


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        """Ответ модели в виде сообщения для истории (нужно для цикла агента)."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.text or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.args, ensure_ascii=False)},
                    **c.extra,          # возвращаем модели её служебные поля как есть
                }
                for c in self.tool_calls
            ]
        return msg


def tool_result(call_id: str, result: Any) -> dict:
    """Результат инструмента в формате сообщения для модели."""
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }


def make_tool(name: str, description: str, params_model) -> dict:
    """Схема инструмента из Pydantic-модели параметров."""
    schema = params_model.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": schema},
    }


async def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> LLMResponse:
    model = model or MODEL
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.3}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = None
    for attempt in range(4):
        try:
            r = await _client.chat.completions.create(**kwargs)
            if r.choices:                      # пустой ответ = сбой провайдера, пробуем ещё
                resp = r
                break
            print(f"   ⚠️ {model}: пустой ответ от провайдера")
        except (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError) as e:
            print(f"   ⏳ {model}: временная ошибка ({type(e).__name__}), повтор…")
        except Exception as e:                 # 400, 401, 404 и т.п. — повторять бесполезно
            print(f"   ❌ {model}: {e}")       # тут виден текст ошибки от провайдера
            break
        await asyncio.sleep(5 * (attempt + 1))  # 5, 10, 15 секунд

    if resp is None:
        if FALLBACK_MODEL and model != FALLBACK_MODEL:
            print(f"   🔁 Переключаюсь на запасную модель {FALLBACK_MODEL}")
            return await chat(messages, tools, model=FALLBACK_MODEL)
        raise RuntimeError("Модель недоступна — попробуйте позже или смените LLM_MODEL в .env")

    msg = resp.choices[0].message
    calls = []
    for c in msg.tool_calls or []:
        try:
            args = json.loads(c.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append(ToolCall(id=c.id, name=c.function.name, args=args,
                              extra=dict(getattr(c, "model_extra", None) or {})))
    return LLMResponse(text=msg.content or "", tool_calls=calls)