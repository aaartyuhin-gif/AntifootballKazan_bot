import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()]

# Клуб
CLUB_NAME: str = os.getenv("CLUB_NAME", "⚽ Футбольный клуб")
CLUB_ADDRESS: str = os.getenv("CLUB_ADDRESS", "ул. Стадионная, 1")
MAX_PLAYERS: int = int(os.getenv("MAX_PLAYERS", "22"))

# ЮKassa
YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET: str = os.getenv("YOOKASSA_SECRET", "")
PAYMENT_RETURN_URL: str = os.getenv("PAYMENT_RETURN_URL", "https://t.me/your_bot")

# БД
DB_PATH: str = os.getenv("DB_PATH", "football.db")
