from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db.models import Media, Post, PostMode, PostStatus, RubricCode, User, UserRole
from bot.db.session import get_session_factory
from bot.keyboards.inline import main_menu_keyboard, review_keyboard, rubric_select_for_post
from bot.services.pipeline import process_text_idea

router = Router()


class IdeaStates(StatesGroup):
    waiting_idea = State()
    waiting_photos = State()


def _format_post_preview(post: Post) -> str:
    rubric_name = post.rubric.value if post.rubric else "не определена"
    hashtags = " ".join(post.hashtags or [])
    return (
        f"📝 <b>Черновик #{post.id}</b>\n"
        f"Рубрика: {rubric_name}\n"
        f"Статус: {post.status.value}\n\n"
        f"<b>VK:</b>\n{post.content_vk}\n\n"
        f"<b>Telegram:</b>\n{post.content_tg}\n\n"
        f"<b>Shorts:</b>\n{post.content_shorts}\n\n"
        f"{hashtags}"
    )


async def _send_post_result(message: Message, post: Post, db_user: User) -> None:
    text = _format_post_preview(post)
    if post.media:
        selected = [m for m in post.media if m.is_selected]
        if selected:
            await message.answer_photo(
                photo=selected[0].telegram_file_id,
                caption=text[:1024],
                reply_markup=review_keyboard(post, db_user.role),
                parse_mode="HTML",
            )
            if len(text) > 1024:
                await message.answer(
                    text[1024:],
                    reply_markup=review_keyboard(post, db_user.role),
                    parse_mode="HTML",
                )
            return
    await message.answer(
        text,
        reply_markup=review_keyboard(post, db_user.role),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "mode:idea")
async def start_idea_mode(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if db_user.role == UserRole.foreman:
        await callback.answer("Прорабу доступен только режим «Голос + фото»", show_alert=True)
        return
    await state.set_state(IdeaStates.waiting_idea)
    await callback.message.answer(
        "💡 Опишите идею для поста текстом.\n"
        "Можно также использовать команду: /идея ваш текст"
    )
    await callback.answer()


@router.message(Command("идея"))
async def cmd_idea(message: Message, db_user: User, state: FSMContext) -> None:
    if db_user.role == UserRole.foreman:
        await message.answer("Прорабу доступен только режим «Голос + фото»")
        return
    text = message.text.replace("/идея", "").strip() if message.text else ""
    if not text:
        await state.set_state(IdeaStates.waiting_idea)
        await message.answer("Опишите идею для поста:")
        return
    await _create_post_from_idea(message, db_user, text, state)


@router.message(IdeaStates.waiting_idea, F.text)
async def receive_idea(message: Message, db_user: User, state: FSMContext) -> None:
    await _create_post_from_idea(message, db_user, message.text, state)


async def _create_post_from_idea(
    message: Message,
    db_user: User,
    text: str,
    state: FSMContext,
) -> None:
    status_msg = await message.answer("⏳ Генерирую пост...")
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = Post(
            author_id=db_user.id,
            mode=PostMode.idea,
            status=PostStatus.draft,
            source_idea=text,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        try:
            post, confidence, needs_clarification = await process_text_idea(
                session, post, text
            )
        except Exception as exc:
            await status_msg.edit_text(f"❌ Ошибка генерации: {exc}")
            return

        result = await session.scalar(
            select(Post)
            .where(Post.id == post.id)
            .options(selectinload(Post.media))
        )

    await state.set_state(IdeaStates.waiting_photos)
    await state.update_data(post_id=post.id)

    await status_msg.delete()
    await _send_post_result(message, result, db_user)

    if confidence < 0.6 or needs_clarification:
        await message.answer(
            "🤔 Рубрика определена неуверенно. Выберите вручную:",
            reply_markup=rubric_select_for_post(post.id),
        )

    await message.answer(
        "📷 Пришлите фото (2-10 шт.) или нажмите /готово для завершения."
    )


@router.message(IdeaStates.waiting_photos, F.photo)
@router.message(IdeaStates.waiting_photos, Command("готово"))
async def receive_photos_or_done(
    message: Message,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")

    if message.text and message.text.startswith("/готово"):
        await state.clear()
        await message.answer("✅ Пост готов!", reply_markup=main_menu_keyboard(db_user.role))
        return

    if not post_id or not message.photo:
        return

    file_id = message.photo[-1].file_id
    session_factory = get_session_factory()

    async with session_factory() as session:
        existing = await session.scalars(
            select(Media).where(Media.post_id == post_id)
        )
        count = len(existing.all())

        if count >= 10:
            await message.answer("Максимум 10 фото. Нажмите /готово")
            return

        session.add(
            Media(
                post_id=post_id,
                telegram_file_id=file_id,
                order_index=count,
                is_selected=True,
            )
        )
        await session.commit()

    await message.answer(f"📷 Фото #{count + 1} добавлено. Ещё фото или /готово")
