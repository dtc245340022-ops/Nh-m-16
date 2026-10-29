import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).with_name("conference.db")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection
