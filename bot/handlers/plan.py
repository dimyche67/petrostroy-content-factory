from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

router = Router()

WEEKLY_PLAN = """📅 <b>Контент-план на неделю</b>

<b>Понедельник 12:00</b> — 🎬 Видео-клип
Короткое видео с объекта, деталь + загадка

<b>Среда 18:00</b> — 📐 Планировка / 🔧 Экспертиза
Разбор планировки или техразбор с объекта

<b>Пятница 12:00</b> — 💡 Лайфхак / ⚔️ Баттл
Полезный совет или голосование

<b>Воскресенье 10:00</b> — 🏠 Дом сдан / 😱 Страшилка
Кейс готового объекта или предупреждение

<i>Рекомендация: 4 поста в неделю, 5-10 минут на каждый через бота.</i>"""


@router.message(Command("план"))
async def cmd_plan(message: Message) -> None:
    await message.answer(WEEKLY_PLAN, parse_mode="HTML")


@router.callback_query(F.data == "cmd:plan")
async def callback_plan(callback: CallbackQuery) -> None:
    await callback.message.answer(WEEKLY_PLAN, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "mode:trend_soon")
async def trend_soon(callback: CallbackQuery) -> None:
    await callback.answer(
        "Тренд-библиотека будет доступна в Фазе 3. Используйте «Своя идея».",
        show_alert=True,
    )
