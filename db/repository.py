"""CRUD S1 — limité aux consultants (le reste viendra aux semaines suivantes)."""
import json
from .database import get_connection


def add_consultant(con, **kw) -> int:
    cols = ("nom", "prenom", "titre", "seniorite", "role_principal",
            "annees_experience", "email", "photo_path", "formation",
            "cv_complet_json", "chemin_cv_source")
    vals = [kw.get(c) for c in cols]
    if isinstance(kw.get("cv_complet_json"), (dict, list)):
        vals[cols.index("cv_complet_json")] = json.dumps(kw["cv_complet_json"], ensure_ascii=False)
    cur = con.execute(
        f"INSERT INTO consultants({','.join(cols)}) VALUES({','.join('?'*len(cols))})", vals)
    con.commit()
    return cur.lastrowid


def list_consultants(con) -> list:
    return con.execute(
        "SELECT * FROM consultants WHERE actif=1 ORDER BY nom, prenom").fetchall()


def get_consultant(con, consultant_id: int):
    return con.execute("SELECT * FROM consultants WHERE id=?", (consultant_id,)).fetchone()


def count_consultants(con) -> int:
    return con.execute("SELECT COUNT(*) FROM consultants WHERE actif=1").fetchone()[0]
