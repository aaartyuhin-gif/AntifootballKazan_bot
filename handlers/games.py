from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import (
    get_upcoming_games, get_game, count_active_bookings,
    get_user_booking, create_booking, cancel_booking, get_game_bookings,
)
from pricing import price_for, price_hint
from keyboards import games_keyboard, game_detail_keyboard, back_btn

router = Router()


async def game_text(game_id: int, user_id: int) -> tuple[str, object]:
    g = await get_game(game_id)
    if not g:
        return "Игра не найдена", back_btn()

    count = await count_active_bookings(game_id)
    price = await price_for(count)
    hint = await price_hint(count)
    booking = await get_user_booking(game_id, user_id)
    is_registered = booking is not None
    is_paid = booking and booking["status"] == "paid"

    status_icons = {"open": "🟢 Открыта", "closed": "🔴 Закрыта", "cancelled": "❌ Отменена"}
    status_label = status_icons.get(g["status"], g["status"])

    text = (
        f"📅 <b>{g['date']} в {g['time']}</b>\n"
        f"🏟 {g['field_name']}\n"
        f"👥 Записалось: <b>{count}/{g['max_players']}</b>\n"
        f"💰 {hint}\n"
        f"📌 Статус: {status_label}\n"
        + (f"\n📝 {g['note']}" if g["note"] else "")
        + "\n"
        + ("\n✅ <b>Ты записан</b>" + (" и <b>оплатил</b>" if is_paid else " (ожидает оплаты)") if is_registered else "")
    )
    kb = game_detail_keyboard(game_id, is_registered, bool(is_paid))
    return text, kb


@router.message(Command("games"))
@router.message(F.text == "📅 Ближайшие игры")
async def cmd_games(message: Message):
    games = await get_upcoming_games()
    if not games:
        await message.answer("😔 Ближайших игр пока нет. Следи за обновлениями!")
        return
    await message.answer("📅 <b>Ближайшие игры:</b>\nВыбери игру для подробностей:", reply_markup=games_keyboard(games))


@router.callback_query(F.data.startswith("game:"))
async def cb_game(call: CallbackQuery):
    game_id = int(call.data.split(":")[1])
    text, kb = await game_text(game_id, call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "back:games")
async def cb_back_games(call: CallbackQuery):
    games = await get_upcoming_games()
    if not games:
        await call.message.edit_text("Ближайших игр нет.")
        return
    await call.message.edit_text("📅 <b>Ближайшие игры:</b>", reply_markup=games_keyboard(games))
    await call.answer()


@router.callback_query(F.data.startswith("join:"))
async def cb_join(call: CallbackQuery):
    game_id = int(call.data.split(":")[1])
    g = await get_game(game_id)
    if not g or g["status"] != "open":
        await call.answer("Запись закрыта.", show_alert=True)
        return

    count = await count_active_bookings(game_id)
    if count >= g["max_players"]:
        await call.answer("😔 Мест нет — все слоты заняты.", show_alert=True)
        return

    existing = await get_user_booking(game_id, call.from_user.id)
    if existing:
        await call.answer("Ты уже записан на эту игру.", show_alert=True)
        return

    price = await price_for(count + 1)
    await create_booking(game_id, call.from_user.id, price)

    # Пересчитываем — сколько теперь
    new_count = await count_active_bookings(game_id)
    from pricing import price_hint
    hint = await price_hint(new_count)

    text, kb = await game_text(game_id, call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer(f"✅ Записан! Текущая цена: {int(price)} ₽. Оплати участие.")


@router.callback_query(F.data.startswith("leave:"))
async def cb_leave(call: CallbackQuery):
    game_id = int(call.data.split(":")[1])
    bk = await get_user_booking(game_id, call.from_user.id)
    if bk and bk["status"] == "paid":
        await call.answer("⚠️ Ты уже оплатил. Для отмены свяжись с организатором.", show_alert=True)
        return
    await cancel_booking(game_id, call.from_user.id)
    text, kb = await game_text(game_id, call.from_user.id)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("❌ Запись отменена.")


@router.callback_query(F.data.startswith("players:"))
async def cb_players(call: CallbackQuery):
    game_id = int(call.data.split(":")[1])
    bookings = await get_game_bookings(game_id)
    if not bookings:
        await call.answer("Список пуст.", show_alert=True)
        return
    lines = [f"👥 <b>Игроки ({len(bookings)}):</b>\n"]
    for i, bk in enumerate(bookings, 1):
        name = bk["full_name"] or f"id{bk['user_id']}"
        paid_icon = "✅" if bk["status"] == "paid" else "⏳"
        lines.append(f"{i}. {paid_icon} {name}")
    await call.message.edit_text("\n".join(lines), reply_markup=back_btn(f"game:{game_id}"))
    await call.answer()
