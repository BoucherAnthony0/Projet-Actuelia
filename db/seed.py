"""Seed idempotent d'une grille tarifaire de démonstration (mode régie, générique).

Usage : python -m db.seed
"""
from .database import get_connection, init_db

GRILLE_DEMO = (
    ("regie", None, "Junior", 650.0),
    ("regie", None, "Confirmé", 850.0),
    ("regie", None, "Senior", 1100.0),
    ("regie", None, "Expert", 1400.0),
)


def seed_grilles(con) -> int:
    inserted = 0
    for mode, client_id, profil, tjm in GRILLE_DEMO:
        exists = con.execute(
            "SELECT 1 FROM grilles_tarifaires WHERE mode=? AND profil_seniorite=? AND client_id IS ?",
            (mode, profil, client_id),
        ).fetchone()
        if not exists:
            con.execute(
                "INSERT INTO grilles_tarifaires(mode, client_id, profil_seniorite, tjm) VALUES(?,?,?,?)",
                (mode, client_id, profil, tjm),
            )
            inserted += 1
    con.commit()
    return inserted


if __name__ == "__main__":
    init_db()
    con = get_connection()
    n = seed_grilles(con)
    print(f"Grille tarifaire de démonstration : {n} ligne(s) insérée(s).")
