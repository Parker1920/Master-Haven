import aiosqlite
import sqlite3
import os
import time
import logging


RESET_DB = True

DB_PATH = os.path.join(os.path.dirname(__file__), "xp.db")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
CONFIG = {
  "xp": {
    "primary_per_message": 1,
    "office_xp": 2,
    "keyword_bonus": 1,
    "primary_cooldown": 5
  },

  "xp_bonus": {
    "base_discovery_xp": 5,
    "role_match": 3,
    "cross_role_penalty": -1,
    "channel_match": 1,
    "discovery_cooldown": 30
  },

  "xp_enabled_channels": [
    1423941006142996524,
    1435648667460567132,
    1435647944807288903,
    1435648417425522830,
    1455986568065192205,
    1428169589358854306,
    1423941006142996523,
    1428169589358854306
  ],

  "leveling": {
    "max_level": 10,
    "global_xp": True
  },

  "ranks": [
    {
      "name": "Initiate",
      "min_level": 1,
      "max_level": 3,
      "xp_per_level": 100
    },
    {
      "name": "Advanced",
      "min_level": 4,
      "max_level": 6,
      "xp_per_level": 250
    },
    {
      "name": "Senior",
      "min_level": 7,
      "max_level": 9,
      "xp_per_level": 300,
      "on_reach_level": 7,
      "dm": {
        "message": "Congratulations, Voyager! The next rank comes with more perms, but some expected responsibility. You must submit a ticket to 1434762611504713829 if you are interested in earning Senior rank."
      }
    },
    {
      "name": "Voyager",
      "min_level": 10,
      "max_level": 10,
      "xp_required": 1500,
      "on_reach_level": 10,
      "dm": {
        "message": "You have reached Voyager. Please submit a ticket for final evaluation to receive full Voyager permissions."
      }
    }
  ],

  "roles": {
    "cartographer": {
      "channels": [1432875588602822966, 1434721861664641134],
      "upload_channels": [1495581094899355819, 1495919097936871525],
      "office_channel": 1456660468985888779,
    },

    "xenobiologist": {
      "channels": [1434795794074173471, 1494185313952595978],
      "upload_channels": [1495526495806816398, 1495526887848542279],
      "office_channel": 1434648413814788266,
    },

    "engineer": {
      "channels": [1435391496848146442, 1435391292552249547],
      "upload_channels": [
        1495523249751064757,
        1495524111470821447,
        1495527489659994332,
        1495526178650325228
      ],
      "office_channel": 1445469006407536833,
    },

    "architect": {
      "channels": [1494185916023963749, 1434748205509382224],
      "upload_channels": [1495580592782442666, 1495528051474432143],
      "office_channel": 1441664283418296392,
    },

    "historian": {
      "channels": [1484794285898596485],
      "upload_channels": [
        1495963080847261796,
        1495963305192456334,
        1495963517650473001
      ],
      "office_channel": 1495922234219565259,
    },

    "diplomat": {
      "channels": [1435648549147901962],
      "office_channel": 1435648549147901962,
    }
  }
}

PRIMARY_ROLE_MAP = {
    "cartographer": 1491574891089232064,
    "xenobiologist": 1491575043371827250,
    "diplomat": 1491575217288646857,
    "architect": 1491575562760622140,
    "engineer": 1491575668046037143,
    "historian": 1491575761570631842,
}

# ---------------- CONNECTION ----------------
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
async def migrate(db):
    await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, primary_role TEXT)")
    

async def init_db():
    log.info("init_db() started")
    if RESET_DB and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, primary_role TEXT)")
        await db.execute("PRAGMA journal_mode=WAL;")
        await migrate(db)
        await db.commit()
        await db.execute("""
        CREATE TABLE IF NOT EXISTS panels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            message_id INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            primary_role TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER,
            role TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            PRIMARY KEY(user_id, role)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER,
            key TEXT,
            last_used REAL,
            PRIMARY KEY(user_id, key)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS global_levels (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            senior_dm_sent INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        UPDATE user_roles
        SET level = 1
        WHERE typeof(level) = 'text'
        """)

        await db.commit()
        log.info("init_db() finished")
    
async def system_xp(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            INSERT OR IGNORE INTO user_xp (user_id, xp)
            VALUES (?, 0)
        """, (user_id,))

        await db.execute("""
            UPDATE user_xp
            SET xp = xp + ?
            WHERE user_id = ?
        """, (amount, user_id))

        await db.commit()
        
# ---------------- CONFIG HELPERS ----------------
def get_cfg(key, default=0):
    section, sub = key.split(".")
    return CONFIG.get(section, {}).get(sub, default)

# ---------------- DB HELPERS ----------------
def get_rank(level):
    """
    Returns the rank dict that matches the user's level.
    Falls back to highest valid rank if level exceeds defined ranges.
    """

    ranks = CONFIG.get("ranks", [])

    for rank in ranks:
        min_level = rank.get("min_level")
        max_level = rank.get("max_level")

        if min_level is None and max_level is None:
            if rank.get("level") == level:
                return rank
            continue

        if min_level <= level <= max_level:
            return rank

    fallback = None
    for rank in ranks:
        if rank.get("min_level", 0) <= level:
            fallback = rank

    return fallback

def get_rank_name(level: int, role: str):
    role_id = PRIMARY_ROLE_MAP.get(role.lower())
    role = role.lower().replace("primary", "").strip()
    role_name = role.capitalize() if role_id is None else role.capitalize()

    rank = next(
        r for r in CONFIG["ranks"]
        if r["min_level"] <= level <= r["max_level"]
    )

    return f"{rank['name']} {role_name}"

async def ensure_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def get_xp(user_id, role):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT xp FROM user_roles WHERE user_id=? AND role=?",
            (user_id, role)
        )

        row = await cur.fetchone()
        await cur.close()

    return row[0] if row else 0

async def add_xp(user_id, role, amount):
    try:
        await ensure_user(user_id)
    
        async with aiosqlite.connect(DB_PATH) as db:
    
            await db.execute("""
            INSERT OR IGNORE INTO user_roles (user_id, role, xp, level)
            VALUES (?, ?, 0, 1)
            """, (user_id, role))
    
            cur = await db.execute("""
            SELECT xp, level
            FROM user_roles
            WHERE user_id=? AND role=?
            """, (user_id, role))
    
            row = await cur.fetchone()
    
            xp, old_level = row
            level=int(old_level)
            if level == 0:
                level = 1
    
            xp += amount
    
            while level < CONFIG["leveling"]["max_level"]:
                needed = get_rank(level, role)["xp_per_level"]
    
                if xp < needed:
                    break
    
                xp -= needed
                level += 1
    
            old_rank = get_rank_name(old_level, role)
            new_rank = get_rank_name(level, role)
    
            await db.execute("""
            UPDATE user_roles
            SET xp=?, level=?
            WHERE user_id=? AND role=?
            """, (xp, level, user_id, role))
    
            await db.commit()
    
        leveled_up = int(level) > int(old_level)
        
        
        log.info(f"XP ADD -> user={user_id} role={role} amount={amount}")
    
        return xp, level, leveled_up
    
    except Exception:
        log.exception("XP error")
        raise

async def get_level(user_id, role):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT level FROM user_roles WHERE user_id=? AND role=?",
            (user_id, role)
        )

        row = await cur.fetchone()
        await cur.close()

    return row[0] if row else 1


async def set_level(user_id, role, level):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE user_roles
            SET level=?
            WHERE user_id=? AND role=?
        """, (level, user_id, role))

        await db.commit()

async def save_panel(guild_id, channel_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO panels (guild_id, channel_id, message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET channel_id=excluded.channel_id,
                          message_id=excluded.message_id
        """, (guild_id, channel_id, message_id))

        await db.commit()


async def get_panel(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT channel_id, message_id
            FROM panels
            WHERE guild_id=?
        """, (guild_id,))

        row = await cur.fetchone()
        await cur.close()

    return row


# ---------------- COOLDOWNS ----------------
cooldowns = {}

def check_cooldown(user_id, key, cooldown):
    now = time.time()

    cache_key = f"{user_id}:{key}"

    last = cooldowns.get(cache_key, 0)

    if now - last < cooldown:
        return False

    cooldowns[cache_key] = now
    return True


# ---------------- GLOBAL XP ----------------
async def get_global(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO global_levels (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()

        cur = await db.execute("""
            SELECT xp, level, senior_dm_sent
            FROM global_levels
            WHERE user_id=?
        """, (user_id,))

        row = await cur.fetchone()
        await cur.close()

    return row


async def save_global(user_id, xp, level, dm_flag):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE global_levels
            SET xp=?, level=?, senior_dm_sent=?
            WHERE user_id=?
        """, (xp, level, dm_flag, user_id))

        await db.commit()
        await cur.close()

    return xp, level, dm_flag
