from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Ближайшие игры"), KeyboardButton(text="📋 Мои записи")],
            [KeyboardButton(text="💰 Цены"),           KeyboardButton(text="ℹ️ О клубе")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать игру"),    KeyboardButton(text="🎮 Управление играми")],
            [KeyboardButton(text="⚙️ Настройки цен"),  KeyboardButton(text="👥 Игроки")],
            [KeyboardButton(text="📢 Рассылка"),        KeyboardButton(text="🔙 Выйти из админки")],
        ],
        resize_keyboard=True,
    )


def games_keyboard(games: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in games:
        from database import count_active_bookings
        label = f"📅 {g['date']} {g['time']} — {g['field_name']}"
        b.button(text=label, callback_data=f"game:{g['id']}")
    b.adjust(1)
    return b.as_markup()


def game_detail_keyboard(game_id: int, is_registered: bool, is_paid: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not is_registered:
        b.button(text="✅ Записаться", callback_data=f"join:{game_id}")
    else:
        if not is_paid:
            b.button(text="💳 Оплатить", callback_data=f"pay:{game_id}")
        b.button(text="❌ Отменить запись", callback_data=f"leave:{game_id}")
    b.button(text="👥 Список игроков", callback_data=f"players:{game_id}")
    b.button(text="◀️ Назад", callback_data="back:games")
    b.adjust(1)
    return b.as_markup()


def pay_keyboard(game_id: int, payment_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Перейти к оплате", url=payment_url)
    b.button(text="✅ Я оплатил — проверить", callback_data=f"check_pay:{game_id}")
    b.button(text="◀️ Назад", callback_data=f"game:{game_id}")
    b.adjust(1)
    return b.as_markup()


def admin_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👥 Игроки + статус оплат", callback_data=f"adm_players:{game_id}")
    b.button(text="✅ Отметить оплату вручную", callback_data=f"adm_mark_paid:{game_id}")
    b.button(text="📢 Напомнить всем",          callback_data=f"adm_notify:{game_id}")
    b.button(text="🚫 Отменить игру",           callback_data=f"adm_cancel:{game_id}")
    b.button(text="◀️ Назад",                   callback_data="adm:games")
    b.adjust(1)
    return b.as_markup()


def admin_games_list_keyboard(games: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in games:
        b.button(text=f"🎮 {g['date']} {g['time']}", callback_data=f"adm_game:{g['id']}")
    b.button(text="◀️ Назад", callback_data="adm:main")
    b.adjust(1)
    return b.as_markup()


def mark_paid_keyboard(game_id: int, bookings: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bk in bookings:
        if bk["status"] != "paid":
            name = bk["full_name"] or f"id{bk['user_id']}"
            b.button(text=f"✅ {name}", callback_data=f"adm_paid:{game_id}:{bk['user_id']}")
    b.button(text="◀️ Назад", callback_data=f"adm_game:{game_id}")
    b.adjust(1)
    return b.as_markup()


def confirm_cancel_keyboard(game_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Да, отменить игру", callback_data=f"adm_cancel_confirm:{game_id}")
    b.button(text="◀️ Нет", callback_data=f"adm_game:{game_id}")
    b.adjust(2)
    return b.as_markup()


def back_btn(cb: str = "back:games") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=cb)]]
    )
