import uuid
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.config import get_settings
from bot.db.models import Media, Post, PostStatus, RubricCode, User, UserRole
from bot.db.session import get_session_factory
from bot.handlers.idea import _format_post_preview, _send_post_result
from bot.keyboards.inline import photo_toggle_keyboard, review_keyboard, rubric_select_for_post
from bot.services.pipeline import process_text_idea

router = Router()


async def _get_post(session, post_id: int) -> Post | None:
    return await session.scalar(
        select(Post)
        .where(Post.id == post_id)
        .options(selectinload(Post.media))
    )


@router.callback_query(F.data.startswith("review:publish:"))
async def publish_post(callback: CallbackQuery, db_user: User) -> None:
    if db_user.role not in (UserRole.marketer, UserRole.owner):
        await callback.answer("Нет доступа", show_alert=True)
        return

    post_id = int(callback.data.split(":")[-1])
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await _get_post(session, post_id)
        if not post:
            await callback.answer("Пост не найден", show_alert=True)
            return

        if post.status == PostStatus.published:
            await callback.answer("Пост уже опубликован", show_alert=True)
            return

        if post.client_request_id:
            await callback.answer("Публикация уже обработана", show_alert=True)
            return

        if settings.require_owner_approval and db_user.role == UserRole.marketer:
            post.status = PostStatus.pending_approval
            await session.commit()
            await callback.message.answer(
                f"📋 Пост #{post_id} отправлен на согласование собственнику."
            )
            await callback.answer()
            return

        post.status = PostStatus.approved
        post.approved_by = db_user.id
        post.approved_at = datetime.utcnow()
        post.client_request_id = str(uuid.uuid4())
        content_vk = post.content_vk
        selected_photos = sum(1 for m in post.media if m.is_selected)
        await session.commit()

    await callback.message.answer(
        f"✅ Пост #{post_id} одобрен!\n\n"
        f"<b>Скопируйте в VK:</b>\n\n{content_vk}\n\n"
        f"📷 Выбранных фото: {selected_photos}",
        parse_mode="HTML",
    )
    await callback.answer("Готово к публикации")


@router.callback_query(F.data.startswith("review:rewrite:"))
async def rewrite_post(callback: CallbackQuery, db_user: User) -> None:
    post_id = int(callback.data.split(":")[-1])
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await _get_post(session, post_id)
        if not post:
            await callback.answer("Пост не найден", show_alert=True)
            return

        source = post.source_transcript or post.source_idea or ""
        if not source:
            await callback.answer("Нет исходного текста", show_alert=True)
            return

        await callback.answer("Переписываю...")
        post, _, _ = await process_text_idea(
            session, post, source, rubric_override=post.rubric
        )
        result = await _get_post(session, post.id)

    await callback.message.answer(
        _format_post_preview(result),
        reply_markup=review_keyboard(result, db_user.role),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("review:rubric:"))
async def change_rubric_menu(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[-1])
    await callback.message.answer(
        "Выберите рубрику:",
        reply_markup=rubric_select_for_post(post_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("change_rubric:"))
async def change_rubric(callback: CallbackQuery, db_user: User) -> None:
    _, post_id_str, rubric_str = callback.data.split(":")
    post_id = int(post_id_str)
    rubric = RubricCode(rubric_str)
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await _get_post(session, post_id)
        if not post:
            await callback.answer("Пост не найден", show_alert=True)
            return

        source = post.source_transcript or post.source_idea or ""
        await callback.answer("Генерирую...")
        post, _, _ = await process_text_idea(
            session, post, source, rubric_override=rubric
        )
        result = await _get_post(session, post.id)

    await callback.message.answer(
        _format_post_preview(result),
        reply_markup=review_keyboard(result, db_user.role),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("review:photos:"))
async def select_photos(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[-1])
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await _get_post(session, post_id)
        if not post or not post.media:
            await callback.answer("Нет фото", show_alert=True)
            return

    await callback.message.answer(
        "Выберите фото для публикации (нажмите, чтобы снять/поставить галочку):",
        reply_markup=photo_toggle_keyboard(post),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("photo:toggle:"))
async def toggle_photo(callback: CallbackQuery) -> None:
    _, _, post_id_str, media_id_str = callback.data.split(":")
    post_id = int(post_id_str)
    media_id = int(media_id_str)
    session_factory = get_session_factory()

    async with session_factory() as session:
        media = await session.get(Media, media_id)
        if media:
            media.is_selected = not media.is_selected
            await session.commit()
        post = await _get_post(session, post_id)

    await callback.message.edit_reply_markup(
        reply_markup=photo_toggle_keyboard(post),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("review:back:"))
async def back_to_post(callback: CallbackQuery, db_user: User) -> None:
    post_id = int(callback.data.split(":")[-1])
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await _get_post(session, post_id)

    await callback.message.answer(
        _format_post_preview(post),
        reply_markup=review_keyboard(post, db_user.role),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("review:delete:"))
async def delete_post(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[-1])
    session_factory = get_session_factory()

    async with session_factory() as session:
        post = await session.get(Post, post_id)
        if post:
            post.status = PostStatus.rejected
            await session.commit()

    await callback.message.answer(f"🗑 Пост #{post_id} удалён (отклонён).")
    await callback.answer()
