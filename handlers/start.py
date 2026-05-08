from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from config import ADMIN_IDS
from database import upsert_user, get_setting
from keyboards import main_menu, admin_menu
from pricing import price_table_text

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    club = await get_setting("club_name", "⚽ Футбольный клуб")
    addr = await get_setting("club_address", "")
    is_admin = message.from_user.id in ADMIN_IDS
    text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"🏟 <b>{club}</b>\n"
        + (f"📍 {addr}\n" if addr else "")
        + "\nЗдесь ты можешь записаться на игру, следить за расписанием и оплатить участие.\n\n"
        "Используй меню ниже 👇"
    )
    kb = admin_menu() if is_admin else main_menu()
    await message.answer(text, reply_markup=kb)


@router.message(Command("admin"))
async def cmd_admin_switch(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer("🔐 Панель администратора", reply_markup=admin_menu())


@router.message(F.text == "🔙 Выйти из админки")
async def exit_admin(message: Message):
    await message.answer("Переключаюсь в режим игрока 👇", reply_markup=main_menu())


@router.message(F.text == "ℹ️ О клубе")
async def about(message: Message):
    club = await get_setting("club_name", "⚽ Футбольный клуб")
    addr = await get_setting("club_address", "")
    max_p = await get_setting("max_players", "22")
    price_text = await price_table_text()
    await message.answer(
        f"🏟 <b>{club}</b>\n"
        + (f"📍 {addr}\n" if addr else "")
        + f"👥 Максимум игроков: {max_p}\n\n"
        + price_text
    )


@router.message(F.text == "💰 Цены")
async def prices(message: Message):
    await message.answer(await price_table_text())
