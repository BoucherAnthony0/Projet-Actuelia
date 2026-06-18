"""CRUD local pour les consultants et les demandes."""
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


def get_or_create_client(
    con,
    nom: str,
    *,
    secteur: str | None = None,
    logo_path: str | None = None,
    notes: str | None = None,
) -> int | None:
    client_nom = (nom or "").strip()
    if not client_nom:
        return None

    row = con.execute("SELECT id FROM clients WHERE nom=?", (client_nom,)).fetchone()
    if row:
        return row["id"]

    cur = con.execute(
        "INSERT INTO clients(nom, secteur, logo_path, notes, nb_demandes) VALUES(?,?,?,?,0)",
        (client_nom, secteur, logo_path, notes),
    )
    con.commit()
    return cur.lastrowid


def create_demande(con, **kw) -> int:
    client_nom = (kw.get("client_nom") or "").strip()
    client_id = kw.get("client_id")
    if client_id is None and client_nom:
        client_id = get_or_create_client(
            con,
            client_nom,
            secteur=kw.get("client_secteur"),
            logo_path=kw.get("client_logo_path"),
        )

    cols = (
        "titre", "reference", "client_nom", "client_logo_path", "client_id",
        "statut", "texte_brut", "analyse_json", "mode_facturation", "nb_jours",
    )
    vals = [
        kw.get("titre"),
        kw.get("reference"),
        client_nom or None,
        kw.get("client_logo_path"),
        client_id,
        kw.get("statut", "brouillon"),
        kw.get("texte_brut"),
        _to_json_string(kw.get("analyse_json")),
        kw.get("mode_facturation"),
        kw.get("nb_jours"),
    ]
    cur = con.execute(
        f"INSERT INTO demandes({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
        vals,
    )
    demande_id = cur.lastrowid
    if client_id is not None:
        _touch_client_demande_count(con, client_id)
    con.commit()
    return demande_id


def set_analyse(
    con,
    demande_id: int,
    analyse_json: dict | list | str,
    *,
    statut: str = "analyse",
) -> None:
    con.execute(
        "UPDATE demandes SET analyse_json=?, statut=? WHERE id=?",
        (_to_json_string(analyse_json), statut, demande_id),
    )
    con.commit()


def add_demande(con, **kw) -> int:
    return create_demande(con, **kw)


def update_demande(con, demande_id: int, **kw) -> None:
    cols = (
        "titre", "reference", "client_nom", "client_logo_path", "client_id",
        "statut", "texte_brut", "analyse_json", "mode_facturation", "nb_jours",
    )
    sets = []
    vals = []
    for col in cols:
        if col in kw:
            value = kw[col]
            if col == "analyse_json":
                value = _to_json_string(value)
            sets.append(f"{col}=?")
            vals.append(value)
    if not sets:
        return
    vals.append(demande_id)
    con.execute(f"UPDATE demandes SET {', '.join(sets)} WHERE id=?", vals)
    con.commit()


def get_demande(con, demande_id: int):
    row = con.execute("SELECT * FROM demandes WHERE id=?", (demande_id,)).fetchone()
    if row is None:
        return None
    return row


def list_demandes(con) -> list:
    return con.execute(
        "SELECT * FROM demandes ORDER BY date_depot DESC, id DESC"
    ).fetchall()


def _touch_client_demande_count(con, client_id: int) -> None:
    con.execute(
        """
        UPDATE clients
        SET nb_demandes=(
            SELECT COUNT(*)
            FROM demandes
            WHERE client_id=?
        ),
            derniere_vue=datetime('now')
        WHERE id=?
        """,
        (client_id, client_id),
    )


def _to_json_string(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
