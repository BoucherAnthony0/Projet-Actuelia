import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import redaction
from db import get_connection, init_db, repository


def test_rediger_contenu_structure_et_editable() -> None:
    fake = {
        "contexte_redige": "Le client souhaite fiabiliser son SI actuariel.",
        "demarche_cadrage": "Cadrage des besoins avec les parties prenantes.",
        "demarche_analyse": "Analyse de l'existant et des risques.",
        "demarche_realisation": "Mise en œuvre des livrables.",
        "demarche_accompagnement": "Accompagnement au changement.",
        "demarche_restitution": "Restitution finale et transfert de compétences.",
    }
    with patch("core.redaction.llm.complete_json", return_value=fake) as mock_complete:
        resultat = redaction.rediger_contenu({"contexte": "...", "objectifs": ["Fiabiliser"]})

    mock_complete.assert_called_once()
    assert resultat["contexte_redige"] == fake["contexte_redige"]
    assert set(resultat["demarche"].keys()) == set(redaction.PHASES_DEMARCHE)
    for phase in redaction.PHASES_DEMARCHE:
        assert resultat["demarche"][phase] == fake[f"demarche_{phase}"]


def test_rediger_contenu_gere_demarche_partielle() -> None:
    with patch("core.redaction.llm.complete_json", return_value={"contexte_redige": "Résumé."}):
        resultat = redaction.rediger_contenu({})

    assert resultat["contexte_redige"] == "Résumé."
    assert resultat["demarche"] == {phase: "" for phase in redaction.PHASES_DEMARCHE}


def test_synthese_cv_ne_pioche_que_dans_le_cv_source() -> None:
    cv = {
        "experiences": [
            {"client": "AssurCo", "role": "Actuaire", "description": "Modèles de provisionnement"},
        ],
        "competences": ["Solvabilité II", "Python"],
    }
    fake = {
        "synthese": "Actuaire ayant modélisé le provisionnement chez AssurCo.",
        "experiences_retenues": ["Modèles de provisionnement chez AssurCo"],
    }
    with patch("core.redaction.llm.complete_json", return_value=fake) as mock_complete:
        resultat = redaction.synthetiser_cv(cv, {"contexte": "Besoin en actuariat IARD"})

    mock_complete.assert_called_once()
    system_prompt = mock_complete.call_args[0][0]
    assert "N'invente RIEN" in system_prompt
    assert resultat["synthese"] == fake["synthese"]
    assert resultat["experiences_retenues"] == fake["experiences_retenues"]


def test_contenu_genere_et_synthese_persistent_et_sont_editables() -> None:
    init_db()
    con = get_connection()

    demande_id = repository.create_demande(
        con, titre="Mission redaction", reference="RFX008792",
        client_nom="Client Redaction", statut="analyse",
    )
    consultant_id = repository.add_consultant(
        con, nom="Dupont", prenom="Alice", seniorite="Senior",
        cv_complet_json={"competences": ["Actuariat"]},
    )
    repository.set_ligne(con, demande_id, consultant_id)

    repository.set_contenu_genere(con, demande_id, {
        "contexte_redige": "Contexte initial.",
        "demarche": {phase: "" for phase in redaction.PHASES_DEMARCHE},
    })
    repository.set_ligne(con, demande_id, consultant_id, synthese_cv="Synthèse initiale.")

    stored = repository.get_demande(con, demande_id)
    contenu = json.loads(stored["contenu_genere_json"])
    assert contenu["contexte_redige"] == "Contexte initial."
    lignes = {row["consultant_id"]: row for row in repository.list_lignes(con, demande_id)}
    assert lignes[consultant_id]["synthese_cv"] == "Synthèse initiale."

    # correction manuelle : le contenu doit rester éditable après une 1ère sauvegarde
    repository.set_contenu_genere(con, demande_id, {**contenu, "contexte_redige": "Contexte corrigé."})
    repository.set_ligne(con, demande_id, consultant_id, synthese_cv="Synthèse corrigée.")

    stored = repository.get_demande(con, demande_id)
    contenu = json.loads(stored["contenu_genere_json"])
    assert contenu["contexte_redige"] == "Contexte corrigé."
    lignes = {row["consultant_id"]: row for row in repository.list_lignes(con, demande_id)}
    assert lignes[consultant_id]["synthese_cv"] == "Synthèse corrigée."

    con.close()
