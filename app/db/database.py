from pathlib import Path
import sqlite3


DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "weather.db"


def init_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                city_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, city_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                push_enabled INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def add_city(user_id: str, city_name: str) -> bool:
    init_storage()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO cities (user_id, city_name) VALUES (?, ?)",
                (user_id, city_name),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_city(user_id: str, city_name: str) -> bool:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM cities WHERE user_id = ? AND city_name = ?",
            (user_id, city_name),
        )
        conn.commit()

    return cursor.rowcount > 0


def list_cities(user_id: str) -> list[str]:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT city_name FROM cities WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()

    return [row[0] for row in rows]


def is_push_enabled(user_id: str) -> bool:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT push_enabled FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    return bool(row[0]) if row else False


def set_push_enabled(user_id: str, enabled: bool) -> None:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, push_enabled)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET push_enabled = excluded.push_enabled
            """,
            (user_id, int(enabled)),
        )
        conn.commit()
