from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database import get_user_bookings
from keyboards import main_menu

router = Router()


@router.message(Command("mybookings"))
@router.message(F.text == "📋 Мои записи")
async def cmd_my_bookings(message: Message):
    bookings = await get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("У тебя нет предстоящих записей.\n\nНажми «📅 Ближайшие игры» чтобы записаться!", reply_markup=main_menu())
        return

    lines = ["📋 <b>Мои записи:</b>\n"]
    for bk in bookings:
        paid_icon = "✅ Оплачено" if bk["status"] == "paid" else "⏳ Ожидает оплаты"
        lines.append(
            f"📅 <b>{bk['date']} в {bk['time']}</b>\n"
            f"🏟 {bk['field_name']}\n"
            f"💰 {int(bk['amount'])} ₽ — {paid_icon}\n"
        )
    await message.answer("\n".join(lines))
