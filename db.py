"""
Initialisation et connexion à la base SQLite locale.

Usage :
    python db.py            # crée actuelia.db à partir de schema.sql
    from db import get_connection
    con = get_connection()  # connexion avec clés étrangères ACTIVÉES
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "actuelia.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion avec FK actives et lignes nommées.

    PRAGMA foreign_keys est PAR CONNEXION dans SQLite : il faut le
    réactiver à chaque ouverture, sinon les contraintes sont ignorées.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row          # accès colonnes par nom
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def init_db() -> None:
    """(Re)crée le schéma. Idempotent grâce aux CREATE TABLE IF NOT EXISTS."""
    con = get_connection()
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    con.commit()
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    con.close()
    print(f"Base initialisée : {DB_PATH}")
    print("Tables :", ", ".join(tables))


if __name__ == "__main__":
    init_db()
