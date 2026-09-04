import base64

import anthropic
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import get_settings
from bot.db.models import Media, Post, PostMode, PostStatus, User, UserRole
from bot.db.session import get_session_factory
from bot.handlers.idea import _send_post_result
from bot.keyboards.inline import main_menu_keyboard, rubric_select_for_post
from bot.services.pipeline import process_text_idea

router = Router()


class PhotoPostStates(StatesGroup):
    waiting_photos = State()
    waiting_more_photos = State()


@router.callback_query(F.data == "mode:photo_post")
async def start_photo_post(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    if db_user.role == UserRole.foreman:
        await callback.answer("Этот режим недоступен для прораба.", show_alert=True)
        return
    await state.set_state(PhotoPostStates.waiting_photos)
    await callback.message.answer(
        "🖼 Пришлите фото с объекта (до 10 шт.).\n"
        "Можно добавить подпись — бот учтёт её при написании поста.\n\n"
        "Когда все фото отправлены — нажмите /готово"
    )
    await callback.answer()


@router.message(PhotoPostStates.waiting_photos, F.photo)
@router.message(PhotoPostStates.waiting_more_photos, F.photo)
async def receive_photos(message: Message, db_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    captions = data.get("captions", [])

    file_id = message.photo[-1].file_id
    photos.append(file_id)
    if message.caption:
        captions.append(message.caption)

    await state.update_data(photos=photos, captions=captions)
    await state.set_state(PhotoPostStates.waiting_more_photos)

    if len(photos) >= 10:
        await message.answer("📷 Максимум 10 фото достигнут. Генерирую пост...")
        await _generate_from_photos(message, db_user, state)
    else:
        await message.answer(f"📷 Фото #{len(photos)} добавлено. Ещё фото или /готово")


@router.message(PhotoPostStates.waiting_more_photos, Command("готово"))
@router.message(PhotoPostStates.waiting_photos, Command("готово"))
async def photos_done(message: Message, db_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("photos"):
        await message.answer("❌ Вы не отправили ни одного фото.")
        return
    await _generate_from_photos(message, db_user, state)


async def _generate_from_photos(message: Message, db_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    captions = data.get("captions", [])

    status = await message.answer("🔍 Анализирую фото...")

    # Download photos and encode to base64
    image_contents = []
    for file_id in photos[:5]:  # limit to 5 images for Claude
        try:
            file = await message.bot.get_file(file_id)
            file_bytes = await message.bot.download_file(file.file_path)
            b64 = base64.b64encode(file_bytes.read()).decode()
            image_contents.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })
        except Exception:
            continue

    if not image_contents:
        await status.edit_text("❌ Не удалось загрузить фото. Попробуйте ещё раз.")
        return

    caption_text = ""
    if captions:
        caption_text = f"\nПодписи от автора: {'; '.join(captions)}"

    image_contents.append({
        "type": "text",
        "text": (
            f"Ты — контент-стратег строительной компании «Петрострой». "
            f"Опиши что видишь на фото со стройки: этап работ, материалы, конструкции, детали. "
            f"Выдели ключевые факты для поста в соцсети.{caption_text}\n"
            f"Ответь кратко: 3-5 предложений с конкретными деталями."
        ),
    })

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        vision_response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": image_contents}],
        )
        description = vision_response.content[0].text
    except Exception as e:
        await status.edit_text(f"❌ Ошибка анализа фото: {e}")
        return

    await status.edit_text("⏳ Пишу пост...")

    session_factory = get_session_factory()
    async with session_factory() as session:
        post = Post(
            author_id=db_user.id,
            mode=PostMode.idea,
            status=PostStatus.draft,
            source_idea=description,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

        # Save photos to post
        for i, file_id in enumerate(photos):
            session.add(Media(
                post_id=post.id,
                telegram_file_id=file_id,
                order_index=i,
                is_selected=(i == 0),
            ))
        await session.commit()

        try:
            post, confidence, needs_clarification = await process_text_idea(
                session, post, description
            )
        except Exception as e:
            await status.edit_text(f"❌ Ошибка генерации поста: {e}")
            return

        result = await session.scalar(
            select(Post).where(Post.id == post.id).options(selectinload(Post.media))
        )

    await status.delete()
    await _send_post_result(message, result, db_user)

    if confidence < 0.6 or needs_clarification:
        await message.answer(
            "🤔 Рубрика определена неуверенно. Выберите вручную:",
            reply_markup=rubric_select_for_post(post.id),
        )

    await state.clear()
