"""Seed idempotent de la grille tarifaire.

Usage : python -m db.seed

Charge data/grille_tarifaire.json s'il existe (grille réelle Actuelia,
fichier local volontairement hors Git — voir .gitignore et README) et
retombe sur une grille de démonstration sinon (dépôt fraîchement cloné, CI).

Format attendu de data/grille_tarifaire.json :
{
  "forfait": {"Associé": {"actuariat": 2360, "non_actuariat": 1888}, ...},
  "regie":   {"Associé": {"actuariat": 1910, "non_actuariat": 1528}, ...}
}
"""
import json

import config
from .database import get_connection, init_db

GRILLE_FILE = config.DATA_DIR / "grille_tarifaire.json"

GRILLE_DEMO = (
    ("regie", None, "Junior", 650.0),
    ("regie", None, "Confirmé", 850.0),
    ("regie", None, "Senior", 1100.0),
    ("regie", None, "Expert", 1400.0),
)


def _grille_depuis_fichier() -> tuple | None:
    if not GRILLE_FILE.exists():
        return None
    data = json.loads(GRILLE_FILE.read_text(encoding="utf-8"))
    rows = []
    for mode, grades in data.items():
        for grade, taux in grades.items():
            if "actuariat" in taux:
                rows.append((mode, None, grade, float(taux["actuariat"])))
            if "non_actuariat" in taux:
                rows.append((mode, None, f"{grade} — Non Actuariat", float(taux["non_actuariat"])))
    return tuple(rows)


def seed_grilles(con) -> int:
    lignes = _grille_depuis_fichier() or GRILLE_DEMO
    inserted = 0
    for mode, client_id, profil, tjm in lignes:
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
    source = "grille réelle (data/grille_tarifaire.json)" if GRILLE_FILE.exists() else "grille de démonstration"
    print(f"Grille tarifaire ({source}) : {n} ligne(s) insérée(s).")
