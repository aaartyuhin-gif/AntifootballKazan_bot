import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database import (
    create_game, get_upcoming_games, get_game, cancel_game,
    get_game_bookings, mark_paid, get_all_users,
    get_pricing_tiers, set_pricing_tiers,
    get_setting, set_setting, count_active_bookings,
)
from keyboards import (
    admin_menu, admin_games_list_keyboard, admin_game_keyboard,
    mark_paid_keyboard, confirm_cancel_keyboard, back_btn,
)
from pricing import price_table_text

logger = logging.getLogger(__name__)
router = Router()


def admin_only(func):
    async def wrapper(obj, *args, **kwargs):
        uid = obj.from_user.id if hasattr(obj, 'from_user') else None
        if uid not in ADMIN_IDS:
            if hasattr(obj, 'answer'):
                await obj.answer("⛔ Нет доступа.")
            return
        return await func(obj, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ── FSM States ────────────────────────────────────────────────────────────────
class CreateGame(StatesGroup):
    date = State()
    time = State()
    max_players = State()
    note = State()


class PricingEdit(StatesGroup):
    waiting = State()


class BroadcastState(StatesGroup):
    text = State()


class SettingsState(StatesGroup):
    key = State()
    value = State()


# ── Create game ────────────────────────────────────────────────────────────────
@router.message(F.text == "➕ Создать игру")
async def start_create_game(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("📅 Введи дату игры в формате <code>ГГГГ-ММ-ДД</code>\nПример: <code>2025-06-15</code>")
    await state.set_state(CreateGame.date)


@router.message(CreateGame.date)
async def game_date(message: Message, state: FSMContext):
    import re
    if not re.match(r"\d{4}-\d{2}-\d{2}", message.text.strip()):
        await message.answer("❌ Неверный формат. Введи дату как <code>ГГГГ-ММ-ДД</code>")
        return
    await state.update_data(date=message.text.strip())
    await message.answer("⏰ Введи время начала в формате <code>ЧЧ:ММ</code>\nПример: <code>19:00</code>")
    await state.set_state(CreateGame.time)


@router.message(CreateGame.time)
async def game_time(message: Message, state: FSMContext):
    import re
    if not re.match(r"\d{2}:\d{2}", message.text.strip()):
        await message.answer("❌ Неверный формат. Введи время как <code>ЧЧ:ММ</code>")
        return
    await state.update_data(time=message.text.strip())
    max_p = await get_setting("max_players", "22")
    await message.answer(f"👥 Максимум игроков? (по умолчанию {max_p}, нажми /skip для пропуска)")
    await state.set_state(CreateGame.max_players)


@router.message(CreateGame.max_players)
async def game_max_players(message: Message, state: FSMContext):
    max_p = await get_setting("max_players", "22")
    if message.text.strip() == "/skip":
        await state.update_data(max_players=int(max_p))
    elif message.text.strip().isdigit():
        await state.update_data(max_players=int(message.text.strip()))
    else:
        await message.answer("Введи число или /skip")
        return
    await message.answer("📝 Добавить заметку к игре? (или /skip)")
    await state.set_state(CreateGame.note)


@router.message(CreateGame.note)
async def game_note(message: Message, state: FSMContext):
    note = "" if message.text.strip() == "/skip" else message.text.strip()
    data = await state.get_data()
    game_id = await create_game(data["date"], data["time"], data["max_players"], note=note)
    await state.clear()
    await message.answer(
        f"✅ <b>Игра создана!</b>\n\n"
        f"📅 {data['date']} в {data['time']}\n"
        f"👥 Мест: {data['max_players']}\n"
        f"🆔 ID: {game_id}\n"
        + (f"📝 {note}" if note else ""),
        reply_markup=admin_menu(),
    )


# ── Manage games ───────────────────────────────────────────────────────────────
@router.message(F.text == "🎮 Управление играми")
async def manage_games(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    games = await get_upcoming_games()
    if not games:
        await message.answer("Ближайших игр нет. Создай новую.", reply_markup=admin_menu())
        return
    await message.answer("🎮 Выбери игру:", reply_markup=admin_games_list_keyboard(games))


@router.callback_query(F.data == "adm:games")
async def cb_adm_games(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔", show_alert=True)
        return
    games = await get_upcoming_games()
    await call.message.edit_text("🎮 Выбери игру:", reply_markup=admin_games_list_keyboard(games))
    await call.answer()


@router.callback_query(F.data.startswith("adm_game:"))
async def cb_adm_game(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    g = await get_game(game_id)
    count = await count_active_bookings(game_id)
    price_text = await price_table_text()
    text = (
        f"🎮 <b>Игра {g['date']} в {g['time']}</b>\n"
        f"👥 Записалось: {count}/{g['max_players']}\n"
        f"📌 Статус: {g['status']}\n\n"
        + price_text
    )
    await call.message.edit_text(text, reply_markup=admin_game_keyboard(game_id))
    await call.answer()


@router.callback_query(F.data.startswith("adm_players:"))
async def cb_adm_players(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    bookings = await get_game_bookings(game_id)
    if not bookings:
        await call.answer("Никто не записался.", show_alert=True)
        return
    lines = [f"👥 <b>Игроки ({len(bookings)}):</b>\n"]
    for i, bk in enumerate(bookings, 1):
        name = bk["full_name"] or f"id{bk['user_id']}"
        status = "✅ оплатил" if bk["status"] == "paid" else "⏳ не оплатил"
        lines.append(f"{i}. {name} — {status} ({int(bk['amount'])} ₽)")
    await call.message.edit_text("\n".join(lines), reply_markup=back_btn(f"adm_game:{game_id}"))
    await call.answer()


@router.callback_query(F.data.startswith("adm_mark_paid:"))
async def cb_adm_mark_paid(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    bookings = await get_game_bookings(game_id)
    unpaid = [b for b in bookings if b["status"] != "paid"]
    if not unpaid:
        await call.answer("Все игроки уже оплатили ✅", show_alert=True)
        return
    await call.message.edit_text(
        "✅ Выбери игрока для отметки оплаты:",
        reply_markup=mark_paid_keyboard(game_id, bookings),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_paid:"))
async def cb_adm_paid(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    _, game_id_str, user_id_str = call.data.split(":")
    game_id, user_id = int(game_id_str), int(user_id_str)
    await mark_paid(game_id, user_id)
    try:
        await call.bot.send_message(user_id, "✅ <b>Твоя оплата подтверждена администратором!</b>\nДо встречи на поле ⚽")
    except Exception:
        pass
    bookings = await get_game_bookings(game_id)
    await call.message.edit_text("Выбери игрока:", reply_markup=mark_paid_keyboard(game_id, bookings))
    await call.answer("✅ Отмечено!")


@router.callback_query(F.data.startswith("adm_notify:"))
async def cb_adm_notify(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    g = await get_game(game_id)
    bookings = await get_game_bookings(game_id)
    sent = 0
    for bk in bookings:
        try:
            await call.bot.send_message(
                bk["user_id"],
                f"⚽ <b>Напоминание!</b>\n\nИгра завтра: <b>{g['date']} в {g['time']}</b>\n🏟 {g['field_name']}",
            )
            sent += 1
        except Exception:
            pass
    await call.answer(f"📢 Отправлено {sent} игрокам", show_alert=True)


@router.callback_query(F.data.startswith("adm_cancel:"))
async def cb_adm_cancel(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    await call.message.edit_text(
        "⚠️ Ты уверен, что хочешь отменить игру? Все игроки получат уведомление.",
        reply_markup=confirm_cancel_keyboard(game_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_cancel_confirm:"))
async def cb_adm_cancel_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    game_id = int(call.data.split(":")[1])
    g = await get_game(game_id)
    bookings = await get_game_bookings(game_id)
    await cancel_game(game_id)
    for bk in bookings:
        try:
            await call.bot.send_message(
                bk["user_id"],
                f"❌ <b>Игра отменена</b>\n\n📅 {g['date']} в {g['time']}\n\nСвяжитесь с организатором по вопросу возврата средств.",
            )
        except Exception:
            pass
    await call.message.edit_text("✅ Игра отменена. Игроки уведомлены.", reply_markup=None)
    await call.answer()


# ── Pricing settings ───────────────────────────────────────────────────────────
@router.message(F.text == "⚙️ Настройки цен")
async def pricing_settings(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    tiers = await get_pricing_tiers()
    tier_str = "\n".join([f"  {t['min_players']} игроков → {int(t['price'])} ₽" for t in tiers])
    await message.answer(
        f"⚙️ <b>Текущие тарифы:</b>\n\n{tier_str}\n\n"
        "Введи новые тарифы в формате (каждый с новой строки):\n"
        "<code>кол-во_игроков:цена</code>\n\n"
        "Пример:\n"
        "<code>6:1500\n8:1200\n10:1000\n12:800\n14:700\n16:600</code>\n\n"
        "Или /skip для отмены"
    )
    await state.set_state(PricingEdit.waiting)


@router.message(PricingEdit.waiting)
async def save_pricing(message: Message, state: FSMContext):
    if message.text.strip() == "/skip":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return
    tiers = []
    errors = []
    for line in message.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().replace(".", "").isdigit():
            errors.append(f"❌ Ошибка в строке: <code>{line}</code>")
            continue
        tiers.append((int(parts[0].strip()), float(parts[1].strip())))
    if errors:
        await message.answer("\n".join(errors) + "\n\nИсправь и отправь снова.")
        return
    if not tiers:
        await message.answer("Тарифы не введены.")
        return
    await set_pricing_tiers(tiers)
    await state.clear()
    result = "\n".join([f"  {t[0]} игроков → {int(t[1])} ₽" for t in sorted(tiers)])
    await message.answer(f"✅ <b>Тарифы обновлены:</b>\n\n{result}", reply_markup=admin_menu())


# ── Players list ───────────────────────────────────────────────────────────────
@router.message(F.text == "👥 Игроки")
async def all_players(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = await get_all_users()
    if not users:
        await message.answer("Пользователей пока нет.")
        return
    lines = [f"👥 <b>Все игроки ({len(users)}):</b>\n"]
    for u in users:
        name = u["full_name"] or f"id{u['tg_id']}"
        uname = f" @{u['username']}" if u["username"] else ""
        lines.append(f"• {name}{uname}")
    await message.answer("\n".join(lines))


# ── Broadcast ──────────────────────────────────────────────────────────────────
@router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("✏️ Введи текст рассылки (или /skip для отмены):")
    await state.set_state(BroadcastState.text)


@router.message(BroadcastState.text)
async def do_broadcast(message: Message, state: FSMContext):
    if message.text.strip() == "/skip":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_menu())
        return
    users = await get_all_users()
    sent = 0
    for u in users:
        try:
            await message.bot.send_message(u["tg_id"], f"📢 {message.text}")
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Рассылка отправлена {sent} пользователям.", reply_markup=admin_menu())
