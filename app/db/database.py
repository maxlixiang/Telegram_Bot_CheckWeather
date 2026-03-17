from pathlib import Path


DATA_DIR = Path("data")


def init_storage() -> None:
    """Prepare local storage directory for future database usage."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
