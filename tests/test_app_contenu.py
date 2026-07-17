"""Tests d'intégration Streamlit (AppTest) : le contenu généré par le LLM
doit réellement s'afficher dans les champs de l'onglet « Contenu généré ».

Régression visée : les widgets à clé ignorent leur paramètre value une fois
la clé en session_state — le texte généré était calculé mais jamais affiché.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from streamlit.testing.v1 import AppTest

from db import get_connection, init_db, repository

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


def _preparer_demande() -> tuple[int, int]:
    init_db()
    con = get_connection()
    demande_id = repository.create_demande(
        con, titre="Mission AppTest", reference="RFX-APPTEST",
        client_nom="ClientTest", statut="analyse",
    )
    repository.set_analyse(con, demande_id, {"contexte": "ctx", "objectifs": ["o"]})
    cid = repository.add_consultant(
        con, nom="Faure", prenom="Zoé", seniorite="Senior",
        cv_complet_json={"competences": ["X"], "experiences": []},
    )
    repository.set_ligne(con, demande_id, cid)
    con.close()
    return demande_id, cid


def _bouton(at: AppTest, libelle: str):
    boutons = [b for b in at.button if b.label == libelle]
    assert boutons, f"bouton {libelle!r} introuvable"
    return boutons[0]


def test_generation_contenu_saffiche_dans_les_champs() -> None:
    demande_id, _ = _preparer_demande()

    # Clés volontairement accentuées + démarche imbriquée : le pire cas réaliste
    # d'un LLM gratuit francophone.
    fake = {
        "contexte_rédigé": "Contexte généré par le LLM.",
        "démarche": {
            "cadrage": "Cadrage généré.",
            "analyse": "Analyse générée.",
            "réalisation": "Réalisation générée.",
            "accompagnement": "Accompagnement généré.",
            "restitution": "Restitution générée.",
        },
    }
    with patch("core.redaction.llm.complete_json", return_value=fake):
        at = AppTest.from_file(APP, default_timeout=30)
        at.run()
        _bouton(at, "Générer le contenu (LLM)").click()
        at.run()

    assert at.session_state[f"contexte_area_{demande_id}"] == "Contexte généré par le LLM."
    assert at.session_state[f"demarche_cadrage_{demande_id}"] == "Cadrage généré."
    assert at.session_state[f"demarche_restitution_{demande_id}"] == "Restitution générée."
    # Et les zones de texte à l'écran reflètent bien ces valeurs.
    valeurs_affichees = [z.value for z in at.text_area]
    assert "Contexte généré par le LLM." in valeurs_affichees
    assert "Cadrage généré." in valeurs_affichees


def test_generation_synthese_saffiche_dans_le_champ() -> None:
    demande_id, cid = _preparer_demande()

    fake = {"synthèse": "Synthèse générée pour Zoé.", "experiences_retenues": ["Exp"]}
    with patch("core.redaction.llm.complete_json", return_value=fake):
        at = AppTest.from_file(APP, default_timeout=30)
        at.run()
        boutons = [b for b in at.button if b.label.startswith("Générer la synthèse CV")]
        assert boutons, "bouton de synthèse introuvable"
        boutons[0].click()
        at.run()

    assert at.session_state[f"synthese_area_{demande_id}_{cid}"] == "Synthèse générée pour Zoé."
    assert "Synthèse générée pour Zoé." in [z.value for z in at.text_area]
