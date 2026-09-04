import json
import re

from bot.config import get_settings
from bot.prompts.system import EXTRACTION_PROMPT
from bot.services.logging_service import estimate_claude_cost, track_latency


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    # extract JSON block if wrapped in ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
    if match:
        cleaned = match.group(1)
    else:
        # find first { ... } or [ ... ]
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if m:
            cleaned = m.group(1)
    return json.loads(cleaned)


async def extract_facts_and_rubric(text: str) -> tuple[dict, int, int, float, int]:
    import anthropic
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async with track_latency() as latency:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": text}],
        )

    raw = response.content[0].text
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        retry = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=EXTRACTION_PROMPT + "\nВерни только валидный JSON.",
            messages=[{"role": "user", "content": text}],
        )
        data = _parse_json(retry.content[0].text)
        response = retry

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = estimate_claude_cost(tokens_in, tokens_out)
    return data, tokens_in, tokens_out, cost, latency[0]
