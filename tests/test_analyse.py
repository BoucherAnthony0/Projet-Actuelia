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
