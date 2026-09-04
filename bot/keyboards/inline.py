from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Post, Rubric, RubricCode, UserRole


def main_menu_keyboard(role: UserRole) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if role in (UserRole.marketer, UserRole.owner):
        builder.row(
            InlineKeyboardButton(text="💡 Своя идея", callback_data="mode:idea"),
        )
        builder.row(
            InlineKeyboardButton(text="📋 Из тренда (скоро)", callback_data="mode:trend_soon"),
        )
    builder.row(
        InlineKeyboardButton(text="🎤 Голос + фото", callback_data="mode:voice"),
        InlineKeyboardButton(text="🖼 Фото + текст", callback_data="mode:photo_post"),
    )
    if role in (UserRole.marketer, UserRole.owner):
        builder.row(
            InlineKeyboardButton(text="📊 Статистика", callback_data="cmd:stat"),
            InlineKeyboardButton(text="📅 План", callback_data="cmd:plan"),
        )
        builder.row(
            InlineKeyboardButton(text="🗓 Контент-план на месяц", callback_data="cmd:month_plan"),
        )
    if role == UserRole.owner:
        builder.row(
            InlineKeyboardButton(text="💰 Расходы", callback_data="cmd:expenses"),
        )
    return builder.as_markup()


def rubric_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = {
        RubricCode.video_clip: "🎬 Видео-клип",
        RubricCode.layout: "📐 Планировка",
        RubricCode.horror: "😱 Страшилка",
        RubricCode.done: "🏠 Дом сдан",
        RubricCode.expertise: "🔧 Экспертиза",
        RubricCode.battle: "⚔️ Баттл",
        RubricCode.lifehack: "💡 Лайфхак",
        RubricCode.team: "👷 Команда",
        RubricCode.status: "🏆 Статус",
    }
    for code, label in labels.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"rubric:{code.value}"))
    return builder.as_markup()


def rubric_select_for_post(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = {
        RubricCode.video_clip: "🎬",
        RubricCode.layout: "📐",
        RubricCode.horror: "😱",
        RubricCode.done: "🏠",
        RubricCode.expertise: "🔧",
        RubricCode.battle: "⚔️",
        RubricCode.lifehack: "💡",
        RubricCode.team: "👷",
        RubricCode.status: "🏆",
    }
    buttons = [
        InlineKeyboardButton(
            text=label,
            callback_data=f"change_rubric:{post_id}:{code.value}",
        )
        for code, label in labels.items()
    ]
    builder.row(*buttons[:5])
    builder.row(*buttons[5:])
    return builder.as_markup()


def review_keyboard(post: Post, role: UserRole) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if role in (UserRole.marketer, UserRole.owner):
        builder.row(
            InlineKeyboardButton(
                text="✅ Опубликовать",
                callback_data=f"review:publish:{post.id}",
            ),
            InlineKeyboardButton(
                text="✏️ Переписать",
                callback_data=f"review:rewrite:{post.id}",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="🔄 Другая рубрика",
                callback_data=f"review:rubric:{post.id}",
            ),
            InlineKeyboardButton(
                text="🖼 Выбрать фото",
                callback_data=f"review:photos:{post.id}",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"review:delete:{post.id}",
            ),
        )
    return builder.as_markup()


def photo_toggle_keyboard(post: Post) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for media in sorted(post.media, key=lambda m: m.order_index):
        mark = "✅" if media.is_selected else "⬜"
        builder.row(
            InlineKeyboardButton(
                text=f"{mark} Фото #{media.order_index + 1}",
                callback_data=f"photo:toggle:{post.id}:{media.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад к посту",
            callback_data=f"review:back:{post.id}",
        )
    )
    return builder.as_markup()


def rubrics_list_keyboard(rubrics: list[Rubric]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rubric in rubrics:
        builder.row(
            InlineKeyboardButton(
                text=f"{rubric.emoji} {rubric.name}",
                callback_data=f"rubric_gen:{rubric.code.value}",
            )
        )
    return builder.as_markup()
