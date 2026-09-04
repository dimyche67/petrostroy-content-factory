from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db.models import Post, PostMode, PostStatus, RubricCode, User, UserRole
from bot.db.session import get_session_factory
from bot.handlers.idea import _send_post_result
from bot.services.month_plan import format_plan_text, generate_month_plan, replace_topic
from bot.services.pipeline import process_text_idea

router = Router()


class MonthPlanStates(StatesGroup):
    reviewing = State()
    waiting_post_num = State()


def _review_keyboard(plan: list[dict]):
    builder = InlineKeyboardBuilder()
    row = []
    for p in plan:
        row.append(InlineKeyboardButton(text=str(p["num"]), callback_data=f"mplan:replace:{p['num']}"))
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="✅ Всё устраивает", callback_data="mplan:approve"))
    return builder.as_markup()


def _pick_post_keyboard(plan: list[dict]):
    builder = InlineKeyboardBuilder()
    row = []
    for p in plan:
        row.append(InlineKeyboardButton(text=str(p["num"]), callback_data=f"mplan:write:{p['num']}"))
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    return builder.as_markup()


@router.message(Command("месяц"))
async def cmd_month_plan(message: Message, db_user: User, state: FSMContext) -> None:
    if db_user.role == UserRole.foreman:
        await message.answer("Эта функция недоступна для прораба.")
        return
    await _start_month_plan(message, state)


@router.callback_query(F.data == "cmd:month_plan")
async def callback_month_plan(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if db_user.role == UserRole.foreman:
        await callback.answer("Эта функция недоступна для прораба.", show_alert=True)
        return
    await callback.answer()
    await _start_month_plan(callback.message, state)


async def _start_month_plan(message: Message, state: FSMContext) -> None:
    status = await message.answer("⏳ Генерирую контент-план на месяц...")
    try:
        plan = await generate_month_plan()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка генерации: {e}")
        return

    await state.set_state(MonthPlanStates.reviewing)
    await state.update_data(plan=_plan_to_serializable(plan))

    await status.delete()
    text = format_plan_text(plan)
    text += "\n\n<i>Нажмите на номер, чтобы заменить тему. Когда всё готово — «Всё устраивает».</i>"
    await message.answer(text, parse_mode="HTML", reply_markup=_review_keyboard(plan))


@router.callback_query(F.data.startswith("mplan:replace:"), MonthPlanStates.reviewing)
async def replace_topic_callback(callback: CallbackQuery, state: FSMContext) -> None:
    num = int(callback.data.split(":")[-1])
    await callback.answer()

    data = await state.get_data()
    plan = _plan_from_serializable(data["plan"])

    status = await callback.message.answer(f"⏳ Генерирую новую тему для поста #{num}...")
    try:
        new_plan = await replace_topic(plan, num)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
        return

    await state.update_data(plan=_plan_to_serializable(new_plan))
    await status.delete()

    text = format_plan_text(new_plan)
    text += "\n\n<i>Нажмите на номер, чтобы заменить тему. Когда всё готово — «Всё устраивает».</i>"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=_review_keyboard(new_plan))


@router.callback_query(F.data == "mplan:approve", MonthPlanStates.reviewing)
async def approve_plan(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    plan = _plan_from_serializable(data["plan"])

    await state.set_state(MonthPlanStates.waiting_post_num)

    text = "✅ План утверждён!\n\nДля какого поста пишем? Нажмите номер:"
    await callback.message.answer(text, reply_markup=_pick_post_keyboard(plan))


@router.callback_query(F.data.startswith("mplan:write:"), MonthPlanStates.waiting_post_num)
async def write_post_from_plan(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    num = int(callback.data.split(":")[-1])
    await callback.answer()

    data = await state.get_data()
    plan = _plan_from_serializable(data["plan"])
    item = next((p for p in plan if p["num"] == num), None)
    if not item:
        await callback.message.answer("❌ Пост не найден.")
        return

    status = await callback.message.answer(
        f"⏳ Генерирую пост #{num}:\n<i>{item['topic']}</i>", parse_mode="HTML"
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        post = Post(
            author_id=db_user.id,
            mode=PostMode.idea,
            status=PostStatus.draft,
            source_idea=item["topic"],
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        try:
            post, confidence, needs_clarification = await process_text_idea(
                session,
                post,
                item["topic"],
                rubric_override=RubricCode(item["rubric"]),
            )
        except Exception as e:
            await status.edit_text(f"❌ Ошибка генерации: {e}")
            return

        result = await session.scalar(
            select(Post).where(Post.id == post.id).options(selectinload(Post.media))
        )

    await status.delete()
    await _send_post_result(callback.message, result, db_user)
    await state.clear()


# date objects are not JSON-serializable

def _plan_to_serializable(plan: list[dict]) -> list[dict]:
    return [{**p, "date": p["date"].isoformat()} for p in plan]


def _plan_from_serializable(plan: list[dict]) -> list[dict]:
    from datetime import date
    return [{**p, "date": date.fromisoformat(p["date"])} for p in plan]
