from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from bot.db.models import GenerationLog, Post, PostStatus, RubricCode, User, UserRole
from bot.db.session import get_session_factory

router = Router()


async def _build_stats_text() -> str:
    session_factory = get_session_factory()
    async with session_factory() as session:
        total = await session.scalar(select(func.count(Post.id)))
        published = await session.scalar(
            select(func.count(Post.id)).where(Post.status == PostStatus.published)
        )
        approved = await session.scalar(
            select(func.count(Post.id)).where(Post.status == PostStatus.approved)
        )
        draft = await session.scalar(
            select(func.count(Post.id)).where(Post.status == PostStatus.draft)
        )

        rubric_stats = await session.execute(
            select(Post.rubric, func.count(Post.id))
            .where(Post.status.in_([PostStatus.published, PostStatus.approved]))
            .group_by(Post.rubric)
        )
        rubric_lines = [
            f"  • {rubric.value if rubric else 'без рубрики'}: {count}"
            for rubric, count in rubric_stats.all()
        ]

    return (
        "📊 <b>Статистика Контент-завода</b>\n\n"
        f"Всего постов: {total or 0}\n"
        f"Черновики: {draft or 0}\n"
        f"Одобрено: {approved or 0}\n"
        f"Опубликовано: {published or 0}\n\n"
        f"<b>По рубрикам:</b>\n"
        + ("\n".join(rubric_lines) if rubric_lines else "  пока нет данных")
    )


async def _build_expenses_text() -> str:
    session_factory = get_session_factory()
    month_ago = datetime.utcnow() - timedelta(days=30)

    async with session_factory() as session:
        total_cost = await session.scalar(
            select(func.sum(GenerationLog.cost_rub)).where(
                GenerationLog.created_at >= month_ago
            )
        )
        by_operation = await session.execute(
            select(GenerationLog.operation, func.sum(GenerationLog.cost_rub))
            .where(GenerationLog.created_at >= month_ago)
            .group_by(GenerationLog.operation)
        )

    lines = [
        f"  • {op}: {cost:.2f} ₽" for op, cost in by_operation.all()
    ]
    return (
        "💰 <b>Расходы на ИИ за 30 дней</b>\n\n"
        f"Итого: {total_cost or 0:.2f} ₽\n\n"
        f"<b>По операциям:</b>\n"
        + ("\n".join(lines) if lines else "  пока нет данных")
    )


@router.message(Command("стат"))
async def cmd_stat(message: Message) -> None:
    text = await _build_stats_text()
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "cmd:stat")
async def callback_stat(callback: CallbackQuery) -> None:
    text = await _build_stats_text()
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(Command("расходы"))
async def cmd_expenses(message: Message, db_user: User) -> None:
    if db_user.role != UserRole.owner:
        await message.answer("Команда доступна только собственнику")
        return
    text = await _build_expenses_text()
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "cmd:expenses")
async def callback_expenses(callback: CallbackQuery, db_user: User) -> None:
    if db_user.role != UserRole.owner:
        await callback.answer("Только для собственника", show_alert=True)
        return
    text = await _build_expenses_text()
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
