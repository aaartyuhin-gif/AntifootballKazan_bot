import uuid
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET, PAYMENT_RETURN_URL
from database import (
    get_game, get_user_booking, set_payment_id,
    mark_paid, mark_paid_by_payment_id, count_active_bookings,
)
from keyboards import pay_keyboard, back_btn
from pricing import price_for

logger = logging.getLogger(__name__)
router = Router()

YOOKASSA_ENABLED = bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET)

if YOOKASSA_ENABLED:
    from yookassa import Configuration, Payment as YKPayment
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET


async def create_yookassa_payment(amount: float, description: str) -> tuple[str, str]:
    """Создаёт платёж. Возвращает (payment_id, confirmation_url)."""
    payment = YKPayment.create({
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": PAYMENT_RETURN_URL},
        "capture": True,
        "description": description,
    }, uuid.uuid4())
    return payment.id, payment.confirmation.confirmation_url


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery):
    game_id = int(call.data.split(":")[1])
    g = await get_game(game_id)
    bk = await get_user_booking(game_id, call.from_user.id)

    if not bk:
        await call.answer("Сначала запишись на игру.", show_alert=True)
        return
    if bk["status"] == "paid":
        await call.answer("✅ Ты уже оплатил эту игру!", show_alert=True)
        return

    count = await count_active_bookings(game_id)
    amount = await price_for(count)
    description = f"Игра {g['date']} {g['time']} — {g['field_name']}"

    if YOOKASSA_ENABLED:
        try:
            payment_id, pay_url = await create_yookassa_payment(amount, description)
            await set_payment_id(game_id, call.from_user.id, payment_id)
            await call.message.edit_text(
                f"💳 <b>Оплата участия</b>\n\n"
                f"📅 {g['date']} в {g['time']}\n"
                f"💰 Сумма: <b>{int(amount)} ₽</b>\n\n"
                "Нажми кнопку ниже для оплаты через ЮKassa.",
                reply_markup=pay_keyboard(game_id, pay_url),
            )
        except Exception as e:
            logger.error(f"ЮKassa error: {e}")
            await call.answer("Ошибка платёжной системы. Попробуй позже.", show_alert=True)
    else:
        # Режим без ЮKassa — показываем реквизиты / отмечаем вручную
        await call.message.edit_text(
            f"💳 <b>Оплата участия</b>\n\n"
            f"📅 {g['date']} в {g['time']}\n"
            f"💰 Сумма: <b>{int(amount)} ₽</b>\n\n"
            "⚠️ Онлайн-оплата настраивается через ЮKassa (YOOKASSA_SHOP_ID в .env).\n\n"
            "Пока оплата подтверждается администратором вручную.\n"
            "Свяжитесь с организатором для оплаты.",
            reply_markup=back_btn(f"game:{game_id}"),
        )
    await call.answer()


@router.callback_query(F.data.startswith("check_pay:"))
async def cb_check_pay(call: CallbackQuery):
    """Проверка статуса платежа в ЮKassa."""
    game_id = int(call.data.split(":")[1])
    bk = await get_user_booking(game_id, call.from_user.id)

    if not bk:
        await call.answer("Запись не найдена.", show_alert=True)
        return
    if bk["status"] == "paid":
        await call.answer("✅ Оплата уже подтверждена!", show_alert=True)
        return

    if YOOKASSA_ENABLED and bk["payment_id"]:
        try:
            payment = YKPayment.find_one(bk["payment_id"])
            if payment.status == "succeeded":
                await mark_paid(game_id, call.from_user.id)
                await call.answer("✅ Оплата подтверждена!", show_alert=True)
                await call.message.edit_text(
                    "✅ <b>Оплата прошла успешно!</b>\n\nДо встречи на поле! ⚽",
                    reply_markup=back_btn(f"game:{game_id}"),
                )
                return
        except Exception as e:
            logger.error(f"ЮKassa check error: {e}")

    await call.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.", show_alert=True)


# Webhook от ЮKassa (если используется)
@router.message(Command("yookassa_webhook"))
async def handle_webhook(message: Message):
    pass  # Реализуется через aiohttp endpoint отдельно
