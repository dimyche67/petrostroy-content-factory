from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Post, PostMode, PostStatus, RubricCode
from bot.services.correction import correct_transcript
from bot.services.extraction import extract_facts_and_rubric
from bot.services.generation import generate_post_content
from bot.services.logging_service import log_generation
from bot.services.transcription import transcribe_voice


async def process_text_idea(
    session: AsyncSession,
    post: Post,
    text: str,
    rubric_override: RubricCode | None = None,
) -> tuple[Post, float, bool]:
    extraction, ti, to, cost, latency = await extract_facts_and_rubric(text)
    await log_generation(
        session,
        post_id=post.id,
        operation="extraction",
        model="claude-sonnet-4-6",
        tokens_in=ti,
        tokens_out=to,
        cost_rub=cost,
        latency_ms=latency,
    )

    facts = extraction.get("facts", {})
    suggested = extraction.get("suggested_rubric", "expertise")
    confidence = extraction.get("rubric_confidence", 0.0)
    needs_clarification = extraction.get("needs_clarification", False)

    rubric = rubric_override
    if rubric is None:
        if confidence >= 0.6 and not needs_clarification:
            rubric = RubricCode(suggested)
        else:
            rubric = RubricCode.expertise

    content, ti2, to2, cost2, latency2 = await generate_post_content(
        session, facts, rubric
    )
    await log_generation(
        session,
        post_id=post.id,
        operation="generation",
        model="claude-sonnet-4-6",
        tokens_in=ti2,
        tokens_out=to2,
        cost_rub=cost2,
        latency_ms=latency2,
    )

    post.source_idea = text
    post.facts = facts
    post.rubric = rubric
    post.content_vk = content.get("vk")
    post.content_tg = content.get("telegram")
    post.content_shorts = content.get("shorts_caption")
    post.hashtags = content.get("hashtags", [])
    post.status = PostStatus.draft

    await session.commit()
    await session.refresh(post)
    return post, confidence, needs_clarification


async def process_voice_message(
    session: AsyncSession,
    post: Post,
    file_url: str,
    duration: int,
    rubric_override: RubricCode | None = None,
) -> tuple[Post, float, bool]:
    transcript, whisper_cost, whisper_latency = await transcribe_voice(
        file_url, duration
    )
    await log_generation(
        session,
        post_id=post.id,
        operation="transcription",
        model="whisper-1",
        cost_rub=whisper_cost,
        latency_ms=whisper_latency,
    )

    if not transcript:
        raise ValueError("empty_transcript")

    corrected, ti, to, cost, latency = await correct_transcript(transcript)
    await log_generation(
        session,
        post_id=post.id,
        operation="correction",
        model="claude-sonnet-4-6",
        tokens_in=ti,
        tokens_out=to,
        cost_rub=cost,
        latency_ms=latency,
    )

    post.source_transcript = corrected
    post.mode = PostMode.voice
    await session.commit()

    result_post, confidence, needs_clarification = await process_text_idea(
        session, post, corrected, rubric_override=rubric_override
    )
    return result_post, confidence, needs_clarification
