"""Connexion et initialisation de la base SQLite locale."""
import sqlite3
import config


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def init_db() -> list[str]:
    con = get_connection()
    con.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
    con.commit()
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    con.close()
    return tables


if __name__ == "__main__":
    print("Tables :", ", ".join(init_db()))
