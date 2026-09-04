from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from sqlalchemy.orm import selectinload

from bot.db.models import Post, PostMode, PostStatus, Rubric, RubricCode, User, UserRole
from bot.db.session import get_session_factory
from bot.handlers.idea import _send_post_result
from bot.keyboards.inline import rubrics_list_keyboard
from bot.services.pipeline import process_text_idea

router = Router()


class RubricStates(StatesGroup):
    waiting_text = State()


@router.message(Command("рубрика"))
async def cmd_rubric(message: Message, db_user: User) -> None:
    if db_user.role == UserRole.foreman:
        await message.answer("Прорабу доступен только режим «Голос + фото»")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        rubrics = (await session.scalars(select(Rubric).where(Rubric.is_active.is_(True)))).all()

    await message.answer(
        "Выберите рубрику для генерации:",
        reply_markup=rubrics_list_keyboard(list(rubrics)),
    )


@router.callback_query(F.data.startswith("rubric_gen:"))
async def rubric_selected(callback: CallbackQuery, state: FSMContext) -> None:
    rubric_code = callback.data.split(":")[-1]
    await state.set_state(RubricStates.waiting_text)
    await state.update_data(forced_rubric=rubric_code)
    await callback.message.answer("Опишите тему для выбранной рубрики:")
    await callback.answer()


@router.message(RubricStates.waiting_text, F.text)
async def rubric_idea_text(message: Message, db_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    forced_rubric = data.get("forced_rubric")
    await state.clear()

    status_msg = await message.answer("⏳ Генерирую пост...")
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = Post(
            author_id=db_user.id,
            mode=PostMode.idea,
            status=PostStatus.draft,
            source_idea=message.text,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        try:
            post, _, _ = await process_text_idea(
                session,
                post,
                message.text,
                rubric_override=RubricCode(forced_rubric),
            )
        except Exception as exc:
            await status_msg.edit_text(f"❌ Ошибка: {exc}")
            return

        result = await session.scalar(
            select(Post)
            .where(Post.id == post.id)
            .options(selectinload(Post.media))
        )

    await status_msg.delete()
    await _send_post_result(message, result, db_user)
