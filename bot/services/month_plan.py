import json
from datetime import date, timedelta

import anthropic

from bot.config import get_settings

RUBRIC_LABELS = {
    "video_clip": ("🎬", "Видео-клип"),
    "layout": ("📐", "Планировка"),
    "horror": ("😱", "Страшилка"),
    "done": ("🏠", "Дом сдан"),
    "expertise": ("🔧", "Экспертиза"),
    "battle": ("⚔️", "Баттл"),
    "lifehack": ("💡", "Лайфхак"),
    "team": ("👷", "Команда"),
    "status": ("🏆", "Статус"),
}

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _format_date(d: date) -> str:
    return f"{DAYS_RU[d.weekday()]} {d.day} {MONTHS_RU[d.month]}"


def _post_dates_for_month(start: date) -> list[date]:
    """4 posts per week: Mon, Wed, Fri, Sun — ~16-17 posts per month."""
    target_weekdays = {0, 2, 4, 6}  # Mon, Wed, Fri, Sun
    dates = []
    d = start
    end = date(start.year, start.month + 1 if start.month < 12 else 1,
                1) if start.month < 12 else date(start.year + 1, 1, 1)
    while d < end:
        if d.weekday() in target_weekdays:
            dates.append(d)
        d += timedelta(days=1)
    return dates


async def generate_month_plan(start: date | None = None) -> list[dict]:
    if start is None:
        today = date.today()
        start = date(today.year, today.month, 1)

    post_dates = _post_dates_for_month(start)
    n = len(post_dates)

    rubric_list = "\n".join(
        f"- {code}: {emoji} {name}"
        for code, (emoji, name) in RUBRIC_LABELS.items()
    )

    prompt = f"""Ты — контент-стратег строительной компании «Петрострой» (СПб и Москва). 23 года на рынке, 400+ построенных домов. Газобетон и кирпич. Стиль: конкретика, цифры, без воды.

ВАЖНО: Петрострой строит ЧАСТНЫЕ ДОМА для частных заказчиков. Никаких ЖК, жилых комплексов, многоквартирных домов. Только: загородные дома, дачи, коттеджи, дома для ИЖС.

Составь контент-план на {n} постов. Распредели рубрики равномерно, без двух одинаковых рубрик подряд.

Доступные рубрики:
{rubric_list}

Верни СТРОГО JSON-массив без markdown-обёртки, {n} элементов:
[
  {{"rubric": "код_рубрики", "topic": "конкретная тема поста с деталями"}}
]

Правила для тем:
- Только частное строительство: дома, коттеджи, фундаменты, кровля, стены из газобетона/кирпича
- Конкретные цифры: м², мм, дни, рубли, градусы
- Никаких выдуманных названий объектов, ЖК, адресов
- Разнообразные темы, не повторяй похожие"""

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    items = json.loads(raw)

    plan = []
    for i, (d, item) in enumerate(zip(post_dates, items), start=1):
        code = item["rubric"]
        emoji, name = RUBRIC_LABELS.get(code, ("📌", code))
        plan.append({
            "num": i,
            "date": d,
            "date_str": _format_date(d),
            "rubric": code,
            "rubric_emoji": emoji,
            "rubric_name": name,
            "topic": item["topic"],
        })

    return plan


async def replace_topic(plan: list[dict], num: int) -> list[dict]:
    item = next((p for p in plan if p["num"] == num), None)
    if not item:
        return plan

    emoji, name = RUBRIC_LABELS.get(item["rubric"], ("📌", item["rubric"]))
    existing_topics = "\n".join(
        f"- {p['topic']}" for p in plan if p["num"] != num
    )

    prompt = f"""Придумай ОДНУ новую тему для поста рубрики «{emoji} {name}» компании «Петрострой».

Петрострой строит ЧАСТНЫЕ ДОМА (коттеджи, загородные дома, ИЖС). Газобетон и кирпич. СПб и Москва.

Уже использованные темы (не повторяй):
{existing_topics}

Тема должна быть конкретной: материалы, цифры, реальная ситуация на стройке частного дома. Никаких ЖК и многоквартирных домов.
Верни ТОЛЬКО строку с темой, без кавычек и пояснений."""

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    new_topic = response.content[0].text.strip()
    return [
        {**p, "topic": new_topic} if p["num"] == num else p
        for p in plan
    ]


def format_plan_text(plan: list[dict]) -> str:
    lines = ["📅 <b>Контент-план на месяц</b>\n"]
    for item in plan:
        lines.append(
            f"<b>{item['num']}.</b> {item['date_str']}\n"
            f"   {item['rubric_emoji']} {item['rubric_name']}\n"
            f"   {item['topic']}\n"
        )
    return "\n".join(lines)
