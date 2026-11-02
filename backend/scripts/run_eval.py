"""
Автопрогон тестовых запросов (день 6). Агент получает запрос, а скрипт ведёт диалог
как пользователь: отвечает на уточнение, жмёт первую кнопку в карточках, подтверждает
оформление. В конце — таблица: дошёл ли запрос до заказа и какие нарушения промпта нашлись.

Запуск из папки backend (с .venv, сервер запускать НЕ нужно — агент вызывается напрямую):
    python -m scripts.run_eval 1-8            # запросы 1–8 (зона A)
    python -m scripts.run_eval 9-16           # зона B
    python -m scripts.run_eval 17-24          # зона C
    python -m scripts.run_eval 2 9 17         # отдельные номера

ВАЖНО: один запрос = 10–25 обращений к модели. Лимит Gemini Flash-Lite — 500 в день
и 15 в минуту на проект. Гоняйте по 8 запросов на человека, каждый со СВОИМ ключом в .env.
Результат сохраняется в eval/results_ДАТА_ВРЕМЯ.md
"""
import asyncio
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from agent.core import run_agent

BASE = "Анталья на неделю в ноябре, двое и ребёнок 5 лет, до 200 тысяч"

# Строка — обычный запрос. Кортеж (запрос, изменение) — сначала собираем корзину,
# потом пишем изменение и проверяем пересборку (плашка «Что изменилось»).
QUERIES = {
    1: "Сочи, 10–15 декабря, двое взрослых, до 60 тысяч",
    2: BASE,
    3: "Дубай с 5 по 12 декабря из Петербурга, двое",
    4: (BASE, "А давай на два дня позже"),
    5: (BASE, "Бюджет меньше на 30 тысяч"),
    6: (BASE, "С нами едет собака"),
    7: (BASE, "Только без пересадок"),
    8: (BASE, "Вместо моря — горы"),
    9: "Хочу куда-нибудь к тёплому морю в ноябре, недорого, с ребёнком",
    10: "Хочу тишины и гор, без людей",
    11: "Куда поехать на Новый год вдвоём?",
    12: "Без долгих перелётов, с малышом 2 лет",
    13: "С бабушкой на коляске, к морю",
    14: "Нас шестеро взрослых, хотим в Турцию",
    15: "Хотим покататься на лыжах в январе",
    16: "Только с бесплатной отменой и всё включено",
    17: "5 звёзд, всё включено, до 30 тысяч на неделю на троих",
    18: "Расскажи анекдот",
    19: "Забронируй столик в ресторане",
    20: "хачу на моря с малым, бюджет норм",
    21: "в египет 2 взр 1 реб ноябрь",
    22: "Хочу в Париж завтра",
    23: "На море в июле 2020 года",
    24: "Просто покажи что-нибудь интересное",
}
OFF_TOPIC = {18, 19}                 # тут корзина не нужна: ждём вежливый отказ без карточек
CLARIFY_ANSWER = "Из Москвы, двое взрослых, в ноябре, бюджет до 150 тысяч"
MAX_TURNS = 12
PAUSE = 4                            # секунд между ходами — бережём лимит 15 запросов в минуту
CHOICE_STAGES = {"destination_choice", "hotel_selection", "transport_selection"}


def check_text(text: str, stage: str) -> set[str]:
    """Нарушения правил промпта, которые можно поймать по тексту ответа."""
    flags = set()
    if re.search(r"^\s*(\d+[.)]|[-•*])\s+\S", text, re.M) and stage in CHOICE_STAGES:
        flags.add("список вариантов в тексте")
    if re.search(r"\d[\d\s\u00a0]{2,}\s?(₽|руб)", text) and stage in CHOICE_STAGES:
        flags.add("цены в тексте")
    if "**" in text or re.search(r"^#+\s", text, re.M):
        flags.add("markdown")
    if re.search(r"\b20(1\d|2[0-5])\b", text):
        flags.add("прошлый год в тексте")
    return flags


async def run_query(num: int, query) -> dict:
    base, change = (query, None) if isinstance(query, str) else query
    sid = f"eval_{datetime.now():%H%M%S}_{num}"
    res = {"num": num, "query": base + (f" → «{change}»" if change else ""), "turns": 0,
           "questions": 0, "flags": set(), "status": "", "last": ""}
    text, action, change_sent = base, None, False

    for turn in range(1, MAX_TURNS + 1):
        r = await run_agent(sid, user_text=text, action=action)
        reply, trip = r["reply"], r["trip"]
        stage, cards = trip["stage"], reply["cards"]
        res["turns"], res["last"] = turn, reply["text"]
        res["flags"] |= check_text(reply["text"], stage)
        print(f"   #{num} ход {turn}: этап {stage}, карточки {[c['type'] for c in cards]}")

        if "перегружен" in reply["text"]:
            res["status"] = "⛔ модель недоступна (лимит?)"
            break
        if num in OFF_TOPIC:
            ok = not cards and stage in ("clarifying", "inspiration")
            res["status"] = "✅ вежливый отказ" if ok else "❌ взялся за нецелевое"
            break
        if change_sent:                                  # ответ на изменение условий
            if any(c["type"] == "changes" for c in cards) or \
                    (change.startswith("Вместо") and stage == "destination_choice"):
                res["status"] = "✅ план пересобран"
            else:
                res["status"] = "❌ нет плашки «Что изменилось»"
            break
        if stage == "purchased":
            res["status"] = "✅ оформлено"
            break

        clickable = [c for c in cards if c.get("actions")]
        if trip["cart"]["items"] and not clickable:
            if change:                                   # корзина собрана — меняем условия
                text, action, change_sent = change, None, True
            else:
                text, action = "Подтверждаю, оформляй", None
        elif clickable:
            text, action = None, clickable[0]["actions"][0]
        elif stage in ("clarifying", "inspiration"):
            res["questions"] += 1
            if res["questions"] > 2:
                res["flags"].add("больше 2 уточнений")
                res["status"] = "❌ застрял на уточнениях"
                break
            text, action = CLARIFY_ANSWER, None
        elif stage == "trip_review":
            text, action = "Всё устраивает, проверь и добавь в корзину", None
        else:
            text, action = "Продолжай", None
        await asyncio.sleep(PAUSE)
    else:
        res["status"] = f"❌ не дошёл за {MAX_TURNS} ходов (этап {stage})"
    return res


def parse_args(args: list[str]) -> list[int]:
    nums = []
    for a in args or ["1-24"]:
        if "-" in a:
            lo, hi = map(int, a.split("-"))
            nums += range(lo, hi + 1)
        else:
            nums.append(int(a))
    return [n for n in nums if n in QUERIES]


async def main():
    nums = parse_args(sys.argv[1:])
    print(f"Прогоняю {len(nums)} запросов: {nums}\n")
    results, started = [], time.time()
    for n in nums:
        print(f"▶ #{n}: {QUERIES[n] if isinstance(QUERIES[n], str) else ' → '.join(QUERIES[n])}")
        try:
            r = await run_query(n, QUERIES[n])
        except Exception as e:                           # падение кода — тоже результат теста
            r = {"num": n, "query": str(QUERIES[n]), "turns": 0, "questions": 0,
                 "flags": set(), "status": f"💥 исключение: {type(e).__name__}: {e}", "last": ""}
        results.append(r)
        print(f"   {r['status']}  {', '.join(sorted(r['flags']))}\n")

    ok = sum(r["status"].startswith("✅") for r in results)
    lines = [f"# Прогон {datetime.now():%d.%m.%Y %H:%M} — {ok} из {len(results)} успешно\n",
             "| № | Запрос | Итог | Ходов | Уточнений | Нарушения |", "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['num']} | {r['query']} | {r['status']} | {r['turns']} | {r['questions']} | "
                     f"{', '.join(sorted(r['flags'])) or '—'} |")
    lines.append("\n## Последний ответ агента\n")
    for r in results:
        lines.append(f"**#{r['num']}** {r['last'][:400].replace(chr(10), ' ')}\n")

    out = Path(__file__).parent.parent.parent / "eval" / f"results_{datetime.now():%m%d_%H%M}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Итого: {ok} из {len(results)} ✅  ({time.time() - started:.0f} c)")
    print(f"Отчёт: {out}")


if __name__ == "__main__":
    asyncio.run(main())