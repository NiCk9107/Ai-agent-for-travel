"""
Проверка дня 1: модель вызывает тестовый инструмент.
Запуск из папки backend:  python test_llm.py
"""
import asyncio
from typing import Optional

from pydantic import BaseModel, Field

from agent import llm
from agent.prompts import SYSTEM_PROMPT, state_context
from agent.state import Child, TripState


# Тестовый инструмент: те же поля, что в Requirements
class UpdateRequirementsArgs(BaseModel):
    origin: Optional[str] = Field(None, description="Город вылета")
    month: Optional[str] = Field(None, description="Месяц поездки YYYY-MM")
    adults: Optional[int] = None
    children_ages: list[int] = Field(default_factory=list)
    budget_total_rub: Optional[int] = None
    mood: list[str] = Field(default_factory=list)


TOOLS = [
    llm.make_tool(
        "update_requirements",
        "Вызывай КАЖДЫЙ раз, когда пользователь сообщает что-то о поездке: "
        "откуда, когда, сколько человек, бюджет, пожелания.",
        UpdateRequirementsArgs,
    )
]


def dispatch(name: str, args: dict, state: TripState) -> dict:
    if name == "update_requirements":
        a = UpdateRequirementsArgs(**args)
        r = state.requirements
        for f in ("origin", "month", "adults", "budget_total_rub"):
            if getattr(a, f) is not None:
                setattr(r, f, getattr(a, f))
        if a.children_ages:
            r.children = [Child(age=x) for x in a.children_ages]
        if a.mood:
            r.mood = a.mood
        return {"ok": True, "requirements": r.model_dump(exclude_none=True)}
    return {"error": f"unknown tool {name}"}


async def main():
    state = TripState(session_id="test")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": state_context(state)},
        {"role": "user", "content": "Хочу к тёплому морю в ноябре 2026 из Москвы, нас двое и ребёнок 5 лет, бюджет 150 тысяч"},
    ]

    # Мини-цикл агента (полноценный core.py — задача дня 2)
    for step in range(4):
        resp = await llm.chat(messages, tools=TOOLS)
        if not resp.tool_calls:
            break
        messages.append(resp.as_message())
        for call in resp.tool_calls:
            print(f"🔧 Модель вызвала {call.name}({call.args})")
            result = dispatch(call.name, call.args, state)
            messages.append(llm.tool_result(call.id, result))

    print("\n💬 Ответ агента:\n", resp.text)
    print("\n📦 TripState.requirements:\n", state.requirements.model_dump_json(indent=2, exclude_none=True))
    print("\n📤 public_view для фронта:\n", state.public_view())


if __name__ == "__main__":
    asyncio.run(main())