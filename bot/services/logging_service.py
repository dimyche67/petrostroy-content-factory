import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import GenerationLog


def estimate_claude_cost(tokens_in: int, tokens_out: int) -> float:
    settings = get_settings()
    return (
        tokens_in / 1_000_000 * settings.claude_input_cost_per_1m_rub
        + tokens_out / 1_000_000 * settings.claude_output_cost_per_1m_rub
    )


def estimate_whisper_cost(duration_seconds: float) -> float:
    settings = get_settings()
    minutes = max(duration_seconds / 60, 0.1)
    return minutes * settings.whisper_cost_per_minute_rub


async def log_generation(
    session: AsyncSession,
    *,
    post_id: Optional[int],
    operation: str,
    model: str,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    cost_rub: float = 0.0,
    latency_ms: int = 0,
) -> None:
    session.add(
        GenerationLog(
            post_id=post_id,
            operation=operation,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_rub=cost_rub,
            latency_ms=latency_ms,
        )
    )


@asynccontextmanager
async def track_latency() -> AsyncIterator[list[int]]:
    start = time.perf_counter()
    holder = [0]
    try:
        yield holder
    finally:
        holder[0] = int((time.perf_counter() - start) * 1000)
