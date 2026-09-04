import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Rubric, RubricCode
from bot.prompts.system import GENERATION_PROMPT, SYSTEM_PROMPT
from bot.services.logging_service import estimate_claude_cost, track_latency


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
    if match:
        cleaned = match.group(1)
    else:
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if m:
            cleaned = m.group(1)
    return json.loads(cleaned)


async def get_rubric_prompt(session: AsyncSession, rubric_code: RubricCode) -> Rubric:
    rubric = await session.scalar(select(Rubric).where(Rubric.code == rubric_code))
    if not rubric:
        raise ValueError(f"Rubric {rubric_code} not found")
    return rubric


async def generate_post_content(
    session: AsyncSession,
    facts: dict,
    rubric_code: RubricCode,
) -> tuple[dict, int, int, float, int]:
    import anthropic
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    rubric = await get_rubric_prompt(session, rubric_code)

    facts_str = json.dumps(facts, ensure_ascii=False, indent=2)
    rubric_prompt = rubric.generation_prompt.format(facts=facts_str)

    user_message = (
        f"Рубрика: {rubric.name}\n"
        f"Промт рубрики: {rubric_prompt}\n"
        f"Факты: {facts_str}\n"
        f"Лимиты символов: {rubric.min_chars}-{rubric.max_chars}"
    )

    async with track_latency() as latency:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT + "\n\n" + GENERATION_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

    raw = response.content[0].text
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        retry = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT + "\n\n" + GENERATION_PROMPT + "\nВерни только валидный JSON.",
            messages=[{"role": "user", "content": user_message}],
        )
        data = _parse_json(retry.content[0].text)
        response = retry

    if len(data.get("vk", "")) > 2000:
        data["vk"] = data["vk"][:1997] + "..."
    if len(data.get("telegram", "")) > 1000:
        data["telegram"] = data["telegram"][:997] + "..."

    # Fact-check pass: remove or generalize unverifiable claims
    data = await _fact_check(client, data)

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = estimate_claude_cost(tokens_in, tokens_out)
    return data, tokens_in, tokens_out, cost, latency[0]


FACT_CHECK_PROMPT = """Ты — редактор строительного контента. Проверь тексты постов на фактическую достоверность.

Правила:
1. Убери или замени на общие формулировки любые конкретные цифры, которые ты не можешь подтвердить точно (теплопроводность, марки бетона, конкретные нормы ГОСТ/СНиП с номерами — если не уверен на 100%)
2. Убери выдуманные названия объектов, адреса, имена клиентов
3. Оставь факты, которые являются общеизвестными строительными истинами (физика, принципы, технологии)
4. Не меняй стиль и структуру текста, только убирай недостоверное
5. Если пост корректен — верни без изменений

Верни СТРОГО тот же JSON с теми же ключами, только с исправленными текстами."""


async def _fact_check(client, data: dict) -> dict:
    import anthropic
    post_json = json.dumps(
        {k: v for k, v in data.items() if k in ("vk", "telegram", "shorts_caption")},
        ensure_ascii=False,
        indent=2,
    )

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=FACT_CHECK_PROMPT,
        messages=[{"role": "user", "content": post_json}],
    )

    try:
        checked = _parse_json(response.content[0].text)
        for key in ("vk", "telegram", "shorts_caption"):
            if key in checked:
                data[key] = checked[key]
    except Exception:
        pass  # if parse fails, return original

    return data
