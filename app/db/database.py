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
