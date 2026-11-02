"""
Проверка дня 2: агент проходит весь путь до оформления заказа.
Кнопки «нажимаются» автоматически: берётся первая карточка из прошлого ответа.
Запуск из папки backend:  python test_agent.py
"""
import asyncio
import json

from agent.core import load_state, run_agent

SESSION = "test"


def click_first_card(res: dict) -> dict | None:
    """Нажать «Выбрать» на первой карточке прошлого ответа."""
    cards = res["reply"]["cards"]
    if not cards or not cards[0].get("actions"):
        return None
    return cards[0]["actions"][0]


def show(res: dict):
    print(f"\n💬 {res['reply']['text']}")
    for c in res["reply"]["cards"]:
        title = c.get("title") or c.get("name") or c.get("airline") or c["id"]
        price = c.get("price_total") or c.get("price") or c.get("total") or ""
        print(f"   🃏 [{c['type']}] {c['id']}: {title} {price}")
    t = res["trip"]
    print(f"   ⏩ stage = {t['stage']}, корзина = {t['cart']['total']} ₽, допущения = {t['assumptions']}")


async def main():
    res = await run_agent(SESSION, user_text=(
        "Хочу к тёплому морю в ноябре 2026 из Москвы, нас двое и ребёнок 5 лет, бюджет 150 тысяч"))
    show(res)

    for step in range(8):
        stage = res["trip"]["stage"]
        if stage == "purchased":
            break
        if stage in ("checkout", "trip_review"):
            print("\n👤 Пользователь: Да, всё верно, оформляй")
            res = await run_agent(SESSION, user_text="Да, всё верно, оформляй")
        else:
            action = click_first_card(res)
            if not action:
                print("\n⚠️ Агент не показал карточек — ответим текстом")
                res = await run_agent(SESSION, user_text="Выбери первый вариант и продолжай")
            else:
                print(f"\n👆 Кнопка: {action['type']} {action['payload']}")
                res = await run_agent(SESSION, action=action)
        show(res)

    state = load_state(SESSION)
    print("\n" + ("✅ ДОШЛИ ДО ЗАКАЗА " + state.order_id if state.order_id else "❌ До заказа не дошли"))
    print(json.dumps(state.model_dump(mode="json", exclude={"change_log"}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())