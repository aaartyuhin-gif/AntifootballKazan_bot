import aiosqlite
from contextlib import asynccontextmanager
from config import DB_PATH

CREATE_TABLES = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    tg_id       INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    phone       TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS games (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    time            TEXT NOT NULL,
    max_players     INTEGER NOT NULL,
    status          TEXT DEFAULT 'open',
    field_name      TEXT DEFAULT 'Главное поле',
    note            TEXT DEFAULT '',
    reminder_sent   INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL REFERENCES games(id),
    user_id     INTEGER NOT NULL REFERENCES users(tg_id),
    status      TEXT DEFAULT 'pending',
    payment_id  TEXT,
    amount      REAL,
    paid_at     TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(game_id, user_id)
);

CREATE TABLE IF NOT EXISTS pricing_tiers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    min_players INTEGER NOT NULL,
    price       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

INSERT OR IGNORE INTO settings VALUES ('club_name', 'Антифутбол Казань');
INSERT OR IGNORE INTO settings VALUES ('club_address', '');
INSERT OR IGNORE INTO settings VALUES ('max_players', '22');

INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (6,  1500);
INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (8,  1200);
INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (10, 1000);
INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (12, 800);
INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (14, 700);
INSERT OR IGNORE INTO pricing_tiers (min_players, price) VALUES (16, 600);
"""


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        await db.commit()


async def upsert_user(tg_id: int, username, full_name: str):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users(tg_id,username,full_name) VALUES(?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (tg_id, username, full_name),
        )
        await db.commit()


async def get_all_users():
    async with get_db() as db:
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cur:
            return await cur.fetchall()


async def create_game(date, time, max_players, field_name="Главное поле", note=""):
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO games(date,time,max_players,field_name,note) VALUES(?,?,?,?,?)",
            (date, time, max_players, field_name, note),
        )
        await db.commit()
        return cur.lastrowid


async def get_upcoming_games():
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM games WHERE date >= date('now','localtime') AND status != 'cancelled' ORDER BY date,time"
        ) as cur:
            return await cur.fetchall()


async def get_game(game_id):
    async with get_db() as db:
        async with db.execute("SELECT * FROM games WHERE id=?", (game_id,)) as cur:
            return await cur.fetchone()


async def update_game_status(game_id, status):
    async with get_db() as db:
        await db.execute("UPDATE games SET status=? WHERE id=?", (status, game_id))
        await db.commit()


async def cancel_game(game_id):
    await update_game_status(game_id, "cancelled")


async def get_games_needing_reminder():
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM games
               WHERE reminder_sent=0 AND status='open'
               AND datetime(date||' '||time) BETWEEN datetime('now','localtime','+1 hour')
                                                 AND datetime('now','localtime','+2 hours')"""
        ) as cur:
            return await cur.fetchall()


async def mark_reminder_sent(game_id):
    async with get_db() as db:
        await db.execute("UPDATE games SET reminder_sent=1 WHERE id=?", (game_id,))
        await db.commit()


async def get_game_bookings(game_id):
    async with get_db() as db:
        async with db.execute(
            "SELECT b.*, u.full_name, u.username FROM bookings b "
            "JOIN users u ON b.user_id=u.tg_id WHERE b.game_id=? AND b.status!='cancelled' ORDER BY b.created_at",
            (game_id,),
        ) as cur:
            return await cur.fetchall()


async def count_active_bookings(game_id):
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM bookings WHERE game_id=? AND status!='cancelled'", (game_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0]


async def get_user_booking(game_id, user_id):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM bookings WHERE game_id=? AND user_id=? AND status!='cancelled'",
            (game_id, user_id),
        ) as cur:
            return await cur.fetchone()


async def create_booking(game_id, user_id, amount):
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO bookings(game_id,user_id,amount) VALUES(?,?,?) "
            "ON CONFLICT(game_id,user_id) DO UPDATE SET status='pending', amount=excluded.amount",
            (game_id, user_id, amount),
        )
        await db.commit()
        return cur.lastrowid


async def cancel_booking(game_id, user_id):
    async with get_db() as db:
        await db.execute(
            "UPDATE bookings SET status='cancelled' WHERE game_id=? AND user_id=?",
            (game_id, user_id),
        )
        await db.commit()


async def set_payment_id(game_id, user_id, payment_id):
    async with get_db() as db:
        await db.execute(
            "UPDATE bookings SET payment_id=? WHERE game_id=? AND user_id=?",
            (payment_id, game_id, user_id),
        )
        await db.commit()


async def mark_paid(game_id, user_id):
    async with get_db() as db:
        await db.execute(
            "UPDATE bookings SET status='paid', paid_at=datetime('now','localtime') "
            "WHERE game_id=? AND user_id=?",
            (game_id, user_id),
        )
        await db.commit()


async def mark_paid_by_payment_id(payment_id):
    async with get_db() as db:
        await db.execute(
            "UPDATE bookings SET status='paid', paid_at=datetime('now','localtime') WHERE payment_id=?",
            (payment_id,),
        )
        await db.commit()


async def get_user_bookings(user_id):
    async with get_db() as db:
        async with db.execute(
            "SELECT b.*, g.date, g.time, g.field_name FROM bookings b "
            "JOIN games g ON b.game_id=g.id WHERE b.user_id=? AND g.date>=date('now','localtime') "
            "AND b.status!='cancelled' ORDER BY g.date,g.time",
            (user_id,),
        ) as cur:
            return await cur.fetchall()


async def get_pricing_tiers():
    async with get_db() as db:
        async with db.execute("SELECT * FROM pricing_tiers ORDER BY min_players") as cur:
            return await cur.fetchall()


async def set_pricing_tiers(tiers):
    async with get_db() as db:
        await db.execute("DELETE FROM pricing_tiers")
        await db.executemany("INSERT INTO pricing_tiers(min_players,price) VALUES(?,?)", tiers)
        await db.commit()


def calc_price(player_count, tiers):
    price = tiers[-1]["price"] if tiers else 1000.0
    for tier in sorted(tiers, key=lambda t: t["min_players"]):
        if player_count >= tier["min_players"]:
            price = tier["price"]
    return price


def next_tier(player_count, tiers):
    for tier in sorted(tiers, key=lambda t: t["min_players"]):
        if tier["min_players"] > player_count:
            return tier["min_players"], tier["price"]
    return None


async def get_setting(key, default=""):
    async with get_db() as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key, value):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
