from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db.models import Media, Post, PostMode, PostStatus, User, UserRole
from bot.db.session import get_session_factory
from bot.handlers.idea import _format_post_preview, _send_post_result
from bot.keyboards.inline import main_menu_keyboard, rubric_select_for_post
from bot.services.pipeline import process_voice_message

router = Router()


class VoiceStates(StatesGroup):
    waiting_voice = State()
    waiting_photos = State()


@router.callback_query(F.data == "mode:voice")
async def start_voice_mode(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(VoiceStates.waiting_voice)
    await callback.message.answer(
        "🎤 Наговорите голосовое сообщение с объекта.\n"
        "После расшифровки можно добавить фото (2-10 шт.)."
    )
    await callback.answer()


@router.message(VoiceStates.waiting_voice, F.voice)
@router.message(F.voice)
async def handle_voice(message: Message, db_user: User, state: FSMContext) -> None:
    status_msg = await message.answer("🎧 Расшифровываю голосовое...")

    file = await message.bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"
    duration = message.voice.duration or 30

    session_factory = get_session_factory()

    async with session_factory() as session:
        post = Post(
            author_id=db_user.id,
            mode=PostMode.voice,
            status=PostStatus.draft,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        try:
            post, confidence, needs_clarification = await process_voice_message(
                session,
                post,
                file_url,
                duration,
            )
        except ValueError as exc:
            if str(exc) == "empty_transcript":
                await status_msg.edit_text(
                    "❌ Не удалось распознать голос. Попробуйте ещё раз или напишите текстом."
                )
                return
            await status_msg.edit_text(f"❌ Ошибка: {exc}")
            return
        except Exception as exc:
            await status_msg.edit_text(f"❌ Ошибка обработки: {exc}")
            return

        result = await session.scalar(
            select(Post)
            .where(Post.id == post.id)
            .options(selectinload(Post.media))
        )

    await state.set_state(VoiceStates.waiting_photos)
    await state.update_data(post_id=post.id)

    await status_msg.delete()
    await _send_post_result(message, result, db_user)

    if confidence < 0.6 or needs_clarification:
        await message.answer(
            "🤔 Рубрика определена неуверенно. Выберите вручную:",
            reply_markup=rubric_select_for_post(post.id),
        )

    await message.answer("📷 Теперь пришлите фото (2-10 шт.) или /готово")


@router.message(VoiceStates.waiting_photos, F.photo)
async def receive_voice_photos(
    message: Message,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
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


@router.message(VoiceStates.waiting_photos, Command("готово"))
async def voice_photos_done(message: Message, db_user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer("✅ Пост готов!", reply_markup=main_menu_keyboard(db_user.role))
