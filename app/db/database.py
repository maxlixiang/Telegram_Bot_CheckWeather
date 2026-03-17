from dataclasses import dataclass
from pathlib import Path
import logging
import sqlite3


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "weather.db"
DEFAULT_PUSH_HOUR = 8
DEFAULT_PUSH_MINUTE = 0


@dataclass(slots=True)
class StoredCity:
    id: int
    city_name: str
    display_name: str | None
    latitude: float | None
    longitude: float | None
    normalized_key: str | None


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

        city_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cities)").fetchall()
        }
        if "display_name" not in city_columns:
            conn.execute("ALTER TABLE cities ADD COLUMN display_name TEXT")
        if "latitude" not in city_columns:
            conn.execute("ALTER TABLE cities ADD COLUMN latitude REAL")
        if "longitude" not in city_columns:
            conn.execute("ALTER TABLE cities ADD COLUMN longitude REAL")
        if "normalized_key" not in city_columns:
            conn.execute("ALTER TABLE cities ADD COLUMN normalized_key TEXT")

        settings_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(user_settings)").fetchall()
        }
        if "push_hour" not in settings_columns:
            conn.execute(
                f"ALTER TABLE user_settings ADD COLUMN push_hour INTEGER NOT NULL DEFAULT {DEFAULT_PUSH_HOUR}"
            )
        if "push_minute" not in settings_columns:
            conn.execute(
                f"ALTER TABLE user_settings ADD COLUMN push_minute INTEGER NOT NULL DEFAULT {DEFAULT_PUSH_MINUTE}"
            )

        conn.commit()


def add_city_record(
    user_id: str,
    city_name: str,
    display_name: str,
    latitude: float,
    longitude: float,
    normalized_key: str,
) -> None:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO cities (user_id, city_name, display_name, latitude, longitude, normalized_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, city_name, display_name, latitude, longitude, normalized_key),
        )
        conn.commit()


def find_city_by_normalized_key(user_id: str, normalized_key: str) -> StoredCity | None:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT id, city_name, display_name, latitude, longitude, normalized_key
            FROM cities
            WHERE user_id = ? AND normalized_key = ?
            LIMIT 1
            """,
            (user_id, normalized_key),
        ).fetchone()

    return _row_to_stored_city(row)


def update_city_metadata(
    city_id: int,
    display_name: str,
    latitude: float,
    longitude: float,
    normalized_key: str,
) -> None:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE cities
            SET display_name = ?, latitude = ?, longitude = ?, normalized_key = ?
            WHERE id = ?
            """,
            (display_name, latitude, longitude, normalized_key, city_id),
        )
        conn.commit()


def delete_city(user_id: str, city_name: str) -> bool:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            DELETE FROM cities
            WHERE user_id = ? AND (city_name = ? OR display_name = ?)
            """,
            (user_id, city_name, city_name),
        )
        conn.commit()

    return cursor.rowcount > 0


def list_cities(user_id: str) -> list[StoredCity]:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, city_name, display_name, latitude, longitude, normalized_key
            FROM cities
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()

    return [_row_to_stored_city(row) for row in rows]


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


def get_push_time(user_id: str) -> tuple[int, int]:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT push_hour, push_minute FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if not row:
        return DEFAULT_PUSH_HOUR, DEFAULT_PUSH_MINUTE

    hour = row[0] if row[0] is not None else DEFAULT_PUSH_HOUR
    minute = row[1] if row[1] is not None else DEFAULT_PUSH_MINUTE

    if not 0 <= int(hour) <= 23:
        logger.warning("Invalid stored push_hour '%s'. Falling back to default %s.", hour, DEFAULT_PUSH_HOUR)
        hour = DEFAULT_PUSH_HOUR

    if not 0 <= int(minute) <= 59:
        logger.warning(
            "Invalid stored push_minute '%s'. Falling back to default %s.",
            minute,
            DEFAULT_PUSH_MINUTE,
        )
        minute = DEFAULT_PUSH_MINUTE

    return int(hour), int(minute)


def set_push_time(user_id: str, hour: int, minute: int) -> None:
    init_storage()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, push_enabled, push_hour, push_minute)
            VALUES (?, 0, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                push_hour = excluded.push_hour,
                push_minute = excluded.push_minute
            """,
            (user_id, hour, minute),
        )
        conn.commit()


def _row_to_stored_city(row: sqlite3.Row | tuple | None) -> StoredCity | None:
    if row is None:
        return None

    return StoredCity(
        id=row[0],
        city_name=row[1],
        display_name=row[2],
        latitude=row[3],
        longitude=row[4],
        normalized_key=row[5],
    )
