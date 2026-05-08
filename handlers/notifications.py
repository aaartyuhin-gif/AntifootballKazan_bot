import asyncio
import logging
from aiogram import Bot

from database import get_games_needing_reminder, get_game_bookings, mark_reminder_sent

logger = logging.getLogger(__name__)


async def reminder_loop(bot: Bot):
    """Фоновая задача: каждые 10 минут проверяет игры, которым нужно напоминание за 2 часа."""
    while True:
        try:
            games = await get_games_needing_reminder()
            for g in games:
                bookings = await get_game_bookings(g["id"])
                sent = 0
                for bk in bookings:
                    try:
                        await bot.send_message(
                            bk["user_id"],
                            f"⚽ <b>Напоминание!</b>\n\n"
                            f"Через ~2 часа игра:\n"
                            f"📅 <b>{g['date']} в {g['time']}</b>\n"
                            f"🏟 {g['field_name']}\n\n"
                            "Не опаздывай! 🏃",
                        )
                        sent += 1
                    except Exception:
                        pass
                await mark_reminder_sent(g["id"])
                logger.info(f"Reminder sent for game {g['id']} to {sent} players")
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
        await asyncio.sleep(600)  # каждые 10 минут
