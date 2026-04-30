import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "Data", "xp.db")

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
      "max_level": 10
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
      "rank_roles": {
        "Initiate": 1434716088570216608,
        "Advanced": 1457088694321418373,
        "Senior": 1435144343676649533,
        "Voyager": 1426308934251315304
      }
    },

    "xenobiologist": {
      "channels": [1434795794074173471, 1494185313952595978],
      "upload_channels": [1495526495806816398, 1495526887848542279],
      "office_channel": 1434648413814788266,
      "rank_roles": {
        "Initiate": 1434715809963573388,
        "Advanced": 1457088694321418373,
        "Senior": 1435141378077364274,
        "Voyager": 1433570871540191292
      }
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
      "rank_roles": {
        "Initiate": 1457101973219442738,
        "Advanced": 1457104118828241078,
        "Senior": 1457103687485751501,
        "Voyager": 1457104664100208747
      }
    },

    "architect": {
      "channels": [1494185916023963749, 1434748205509382224],
      "upload_channels": [1495580592782442666, 1495528051474432143],
      "office_channel": 1441664283418296392,
      "rank_roles": {
        "Initiate": 1434719851917738034,
        "Advanced": 1434719002273255454,
        "Senior": 1435142030174060658,
        "Voyager": 1436758936073273545
      }
    },

    "historian": {
      "channels": [1484794285898596485],
      "upload_channels": [
        1495963080847261796,
        1495963305192456334,
        1495963517650473001
      ],
      "office_channel": 1495922234219565259,
      "rank_roles": {
        "Initiate": 1487603963418120273,
        "Advanced": 1487604094003839016,
        "Senior": 1487604191152046232,
        "Voyager": 1487604266200731769
      }
    },

    "diplomat": {
      "channels": [1435648549147901962],
      "office_channel": 1435648549147901962,
      "rank_roles": {
        "Initiate": 1434936345650008144,
        "Advanced": 1434936970567749752,
        "Senior": 1434936555629318267,
        "Voyager": 1427386180193878159
      }
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
    return sqlite3.connect(DB_PATH, check_same_thread=False)
    
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, primary_role TEXT)")

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cur.fetchall()]
    
    
              

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        primary_role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_roles (
        user_id INTEGER,
        role TEXT,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        PRIMARY KEY(user_id, role)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cooldowns (
        user_id INTEGER,
        key TEXT,
        last_used REAL,
        PRIMARY KEY(user_id, key)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS global_levels (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        senior_dm_sent INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()
    
def system_xp(user_id: int, amount: int):
    """Add system XP to a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure user exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_xp (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0
        )
    """)

    # Insert if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO user_xp (user_id, xp)
        VALUES (?, 0)
    """, (user_id,))

    # Add XP
    cursor.execute("""
        UPDATE user_xp
        SET xp = xp + ?
        WHERE user_id = ?
    """, (amount, user_id))

    conn.commit()
    conn.close()

# ---------------- CONFIG HELPERS ----------------
def get_cfg(key, default=0):
    section, sub = key.split(".")
    return CONFIG.get(section, {}).get(sub, default)


# ---------------- DB HELPERS ----------------
def ensure_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def get_xp(user_id, role):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT xp FROM user_roles WHERE user_id=? AND role=?", (user_id, role))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def add_xp(user_id, role, amount):
    ensure_user(user_id)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO user_roles (user_id, role, xp)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, role)
    DO UPDATE SET xp = xp + ?
    """, (user_id, role, amount, amount))

    conn.commit()
    conn.close()


def get_level(user_id, role):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT level FROM user_roles WHERE user_id=? AND role=?", (user_id, role))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 1


def set_level(user_id, role, level):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    UPDATE user_roles SET level=?
    WHERE user_id=? AND role=?
    """, (level, user_id, role))
    conn.commit()
    conn.close()


# ---------------- COOLDOWNS ----------------
def check_cooldown(user_id, key, cooldown):
    now = time.time()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT last_used FROM cooldowns WHERE user_id=? AND key=?", (user_id, key))
    row = cur.fetchone()

    if row and now - row[0] < cooldown:
        conn.close()
        return False

    cur.execute("""
    INSERT OR REPLACE INTO cooldowns (user_id, key, last_used)
    VALUES (?, ?, ?)
    """, (user_id, key, now))

    conn.commit()
    conn.close()
    return True


# ---------------- GLOBAL XP ----------------
def get_global(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT OR IGNORE INTO global_levels (user_id) VALUES (?)", (user_id,))

    cur.execute("""
    SELECT xp, level, senior_dm_sent
    FROM global_levels WHERE user_id=?
    """, (user_id,))

    row = cur.fetchone()
    conn.close()
    return row


def save_global(user_id, xp, level, dm_flag):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    UPDATE global_levels
    SET xp=?, level=?, senior_dm_sent=?
    WHERE user_id=?
    """, (xp, level, dm_flag, user_id))
    

    conn.commit()
    conn.close()

    return xp, level, dm_flag
