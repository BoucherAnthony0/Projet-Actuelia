import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import analyse


def test_analyser_demande_produit_une_structure_complete() -> None:
    fake_response = {
        "contexte": "Le client souhaite moderniser son SI actuariel.",
        "objectifs": ["Fiabiliser les calculs", "Réduire les délais"],
        "enjeux": ["Conformité réglementaire"],
        "livrables": ["Audit", "Plan de migration"],
        "competences": ["Actuariat vie", "Python"],
        "planning": "3 mois",
    }
    with patch("core.analyse.llm.complete_json", return_value=fake_response) as mock_complete:
        resultat = analyse.analyser_demande("texte brut de l'appel d'offres RFX008792")

    mock_complete.assert_called_once()
    assert resultat == fake_response


def test_analyser_demande_gere_les_champs_manquants() -> None:
    with patch("core.analyse.llm.complete_json", return_value={"contexte": "Résumé minimal."}):
        resultat = analyse.analyser_demande("texte")

    assert resultat["contexte"] == "Résumé minimal."
    assert resultat["objectifs"] == []
    assert resultat["enjeux"] == []
    assert resultat["livrables"] == []
    assert resultat["competences"] == []
    assert resultat["planning"] == ""


def test_analyser_demande_tolere_les_cles_en_variantes() -> None:
    # Le LLM gratuit renvoie parfois des clés en anglais / sans accents.
    reponse = {
        "context": "Contexte via clé anglaise.",
        "objectives": ["Objectif A"],
        "challenges": ["Enjeu A"],
        "deliverables": ["Livrable A"],
        "skills": ["Compétence A"],
        "timeline": "6 semaines",
    }
    with patch("core.analyse.llm.complete_json", return_value=reponse):
        resultat = analyse.analyser_demande("texte")

    assert resultat["contexte"] == "Contexte via clé anglaise."
    assert resultat["objectifs"] == ["Objectif A"]
    assert resultat["enjeux"] == ["Enjeu A"]
    assert resultat["livrables"] == ["Livrable A"]
    assert resultat["competences"] == ["Compétence A"]
    assert resultat["planning"] == "6 semaines"


def test_analyser_demande_deballe_un_enrobage_et_convertit_les_chaines() -> None:
    # Certains modèles enrobent ({"analyse": {...}}) et renvoient une liste
    # sous forme de texte multi-lignes.
    reponse = {"analyse": {
        "contexte": "Ctx.",
        "objectifs": "Objectif 1\nObjectif 2",
        "livrables": ["L1"],
    }}
    with patch("core.analyse.llm.complete_json", return_value=reponse):
        resultat = analyse.analyser_demande("texte")

    assert resultat["contexte"] == "Ctx."
    assert resultat["objectifs"] == ["Objectif 1", "Objectif 2"]
    assert resultat["livrables"] == ["L1"]
