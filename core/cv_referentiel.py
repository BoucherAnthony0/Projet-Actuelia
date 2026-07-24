# -*- coding: utf-8 -*-
"""Connecteur « référentiel CV » pour le projet Projet-Actuelia (réponse AO).

À DÉPOSER DANS LE PROJET AO : copier ce fichier dans `core/cv_referentiel.py`
du dépôt Projet-Actuelia (aucune autre dépendance que `requests`).

Rôle : le générateur de CV (ce dépôt-ci) est le référentiel maître des
consultants — Master CV exhaustifs, photos, logos. Le projet AO vient y
piocher au lieu de son import CV basique (S1).

Deux modes d'usage :

1) `synchroniser_vers_sqlite(con)` — LE PLUS SIMPLE : recopie les consultants
   du référentiel dans les tables SQLite existantes du projet AO
   (`consultants`, `consultant_experiences`, `consultant_competences`).
   Le reste de l'app AO (sélection S3, synthèse ciblée, export S4) fonctionne
   alors SANS AUCUNE MODIFICATION : elle voit simplement des profils plus
   riches et toujours à jour. À appeler depuis un bouton « Synchroniser les
   consultants » dans l'écran S1, en remplacement de l'import manuel.

2) `lister_consultants()` / `profil_complet(id)` — accès direct à l'API pour
   un usage plus fin (ex. sélection d'expériences en temps réel).

Configuration : variable d'environnement CV_API_URL
  - développement : http://localhost:3000
  - en réseau     : http://<ip-du-serveur>:3000
"""

import json
import os

import requests

CV_API_URL = os.getenv("CV_API_URL", "http://localhost:3000").rstrip("/")
TIMEOUT = 20


# ---------------------------------------------------------------- accès API

def lister_consultants() -> list[dict]:
    """Liste résumée du référentiel : [{id, firstName, lastName, jobTitle}]."""
    r = requests.get(f"{CV_API_URL}/actuaries", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def profil_complet(actuary_id: str) -> dict:
    """Master CV complet d'un consultant (expériences, compétences, photo...)."""
    r = requests.get(f"{CV_API_URL}/actuaries/{actuary_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def logos_valides() -> dict[str, str]:
    """{nom_client_minuscule: image_data_uri} des logos qualifiés."""
    r = requests.get(f"{CV_API_URL}/logos", params={"status": "validated"}, timeout=TIMEOUT)
    r.raise_for_status()
    return {
        l["clientName"].strip().lower(): l["image"]
        for l in r.json() if l.get("clientName")
    }


# ------------------------------------------------- adaptation au format AO

def _profil_vers_format_ao(p: dict) -> dict:
    """Master CV (API camelCase) -> structure `cv_complet_json` du projet AO."""
    experiences = [
        {
            "client": e.get("client") or "",
            "secteur": e.get("clientSector") or "",
            "role": e.get("title") or "",
            "description": " ".join(
                filter(None, [e.get("context") or "", " ".join(e.get("tasks") or [])])
            ).strip(),
            "domaine": e.get("domain") or "",
            "mots_cles": e.get("keywords") or [],
            "date_debut": e.get("startDate") or "",
            "date_fin": e.get("endDate") or "",
        }
        for e in p.get("experiences", [])
    ]
    formation = " ; ".join(
        filter(None, [
            f"{ed.get('degree', '')} — {ed.get('institution') or ''} ({ed.get('year') or ''})".strip(" —()")
            for ed in p.get("educations", [])
        ])
    )
    return {
        "nom": p.get("lastName", ""),
        "prenom": p.get("firstName", ""),
        "titre": p.get("jobTitle") or "",
        "seniorite": None,
        "annees_experience": p.get("yearsOfExperience"),
        "formation": formation,
        "experiences": experiences,
        "competences": [s.get("name", "") for s in p.get("skills", [])],
    }


# ------------------------------------------------ synchronisation SQLite AO

def synchroniser_vers_sqlite(con) -> dict:
    """Recopie le référentiel dans les tables du projet AO (upsert par nom+prénom).

    Retourne {"crees": n, "mis_a_jour": n}. Les consultants déjà présents sont
    mis à jour (profil, expériences et compétences remplacés) ; les autres créés.
    """
    crees = maj = 0
    for item in lister_consultants():
        p = profil_complet(item["id"])
        fmt = _profil_vers_format_ao(p)

        row = con.execute(
            "SELECT id FROM consultants WHERE lower(nom)=? AND lower(prenom)=?",
            (fmt["nom"].lower(), fmt["prenom"].lower()),
        ).fetchone()

        if row:
            cid = row[0]
            con.execute(
                """UPDATE consultants SET titre=?, annees_experience=?, formation=?,
                   cv_complet_json=?, chemin_cv_source=? WHERE id=?""",
                (fmt["titre"], fmt["annees_experience"], fmt["formation"],
                 json.dumps(fmt, ensure_ascii=False), f"referentiel:{item['id']}", cid),
            )
            con.execute("DELETE FROM consultant_experiences WHERE consultant_id=?", (cid,))
            con.execute("DELETE FROM consultant_competences WHERE consultant_id=?", (cid,))
            maj += 1
        else:
            cur = con.execute(
                """INSERT INTO consultants (nom, prenom, titre, annees_experience,
                   formation, cv_complet_json, chemin_cv_source)
                   VALUES (?,?,?,?,?,?,?)""",
                (fmt["nom"], fmt["prenom"], fmt["titre"], fmt["annees_experience"],
                 fmt["formation"], json.dumps(fmt, ensure_ascii=False),
                 f"referentiel:{item['id']}"),
            )
            cid = cur.lastrowid
            crees += 1

        for e in fmt["experiences"]:
            con.execute(
                """INSERT INTO consultant_experiences
                   (consultant_id, client, secteur, role, description,
                    technologies, date_debut, date_fin)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (cid, e["client"], e["secteur"], e["role"], e["description"],
                 ", ".join(e["mots_cles"]), e["date_debut"], e["date_fin"]),
            )
        for c in fmt["competences"]:
            con.execute(
                "INSERT INTO consultant_competences (consultant_id, libelle) VALUES (?,?)",
                (cid, c),
            )
        con.commit()
    return {"crees": crees, "mis_a_jour": maj}
