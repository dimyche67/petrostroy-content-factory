from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.models import User
from bot.keyboards.inline import main_menu_keyboard

router = Router()


@router.message(CommandStart())
@router.message(Command("старт"))
async def cmd_start(message: Message, db_user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"👋 Привет, {db_user.full_name}!\n\n"
        "Я — Контент-завод Петростроя. Превращаю голос, фото и идеи "
        "в готовые посты для соцсетей.\n\n"
        "Выберите режим:",
        reply_markup=main_menu_keyboard(db_user.role),
    )


@router.callback_query(F.data == "cmd:menu")
async def back_to_menu(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Выберите режим:",
        reply_markup=main_menu_keyboard(db_user.role),
    )
    await callback.answer()
