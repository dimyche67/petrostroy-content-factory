import tempfile
from pathlib import Path

import httpx

from bot.config import get_settings
from bot.services.logging_service import estimate_whisper_cost, track_latency


async def transcribe_voice(file_url: str, duration: int = 30) -> tuple[str, float, int]:
    from openai import AsyncOpenAI
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with httpx.AsyncClient() as http:
        response = await http.get(file_url)
        response.raise_for_status()
        audio_bytes = response.content

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        async with track_latency() as latency:
            with tmp_path.open("rb") as audio_file:
                result = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                )
        text = result.text.strip()
        cost = estimate_whisper_cost(duration)
        return text, cost, latency[0]
    finally:
        tmp_path.unlink(missing_ok=True)
