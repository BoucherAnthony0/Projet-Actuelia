"""Connexion et initialisation de la base SQLite locale."""
import sqlite3
import config


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


_MIGRATIONS_COLONNES = {
    "demandes": [("contenu_genere_json", "TEXT")],
    "demande_consultants": [("synthese_cv", "TEXT")],
}


def _migrer_colonnes_manquantes(con: sqlite3.Connection) -> None:
    """Ajoute les colonnes nullable introduites après la création d'une base existante."""
    for table, colonnes in _MIGRATIONS_COLONNES.items():
        existantes = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for nom, type_sql in colonnes:
            if nom not in existantes:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {type_sql}")
    con.commit()


def init_db() -> list[str]:
    con = get_connection()
    con.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
    con.commit()
    _migrer_colonnes_manquantes(con)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    con.close()
    return tables


if __name__ == "__main__":
    print("Tables :", ", ".join(init_db()))
