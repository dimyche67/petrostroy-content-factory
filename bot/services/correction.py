from bot.config import get_settings
from bot.prompts.glossary import GLOSSARY_PROMPT, GLOSSARY_TERMS
from bot.services.logging_service import estimate_claude_cost, track_latency


async def correct_transcript(text: str) -> tuple[str, int, int, float, int]:
    import anthropic
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = GLOSSARY_PROMPT.format(
        glossary=", ".join(GLOSSARY_TERMS),
        text=text,
    )

    async with track_latency() as latency:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

    corrected = response.content[0].text.strip()
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = estimate_claude_cost(tokens_in, tokens_out)
    return corrected, tokens_in, tokens_out, cost, latency[0]
