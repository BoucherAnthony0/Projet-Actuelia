import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from core import finance, pptx_export


def test_template_disponible_reflete_presence_fichier(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "TEMPLATE_PPTX_PATH", tmp_path / "absent.pptx")
    assert pptx_export.template_disponible() is False

    fichier = tmp_path / "present.pptx"
    fichier.write_bytes(b"")
    monkeypatch.setattr(config, "TEMPLATE_PPTX_PATH", fichier)
    assert pptx_export.template_disponible() is True


def test_generer_pptx_sans_template_leve_erreur_claire(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "TEMPLATE_PPTX_PATH", tmp_path / "absent.pptx")
    with pytest.raises(FileNotFoundError, match="Template PowerPoint introuvable"):
        pptx_export.generer_pptx(
            demande={"titre": "Mission", "reference": "RFX001"},
            lignes=[],
            chemin_sortie=tmp_path / "sortie.pptx",
        )


@pytest.mark.skipif(
    not config.TEMPLATE_PPTX_PATH.exists(),
    reason="data/template_proposition.pptx est un fichier confidentiel local, absent en CI",
)
def test_generer_pptx_avec_le_vrai_template(tmp_path) -> None:
    from pptx import Presentation

    demande = {"titre": "Mission de démonstration RFX000TEST", "reference": "RFX000TEST"}
    lignes = [
        {"prenom": "Alice", "nom": "Dupont", "grade": "Manager 2 (M2)", "seniorite": None,
         "nb_jours": 20, "tjm_applique": 1370},
        {"prenom": "Bob", "nom": "Martin", "grade": "Junior 1 (J1)", "seniorite": None,
         "nb_jours": 15, "tjm_applique": 820},
    ]
    contenu = {
        "contexte_redige": "Le client souhaite fiabiliser son processus de test RFX000TEST.",
        "demarche": {
            "cadrage": "Ateliers de cadrage de démonstration.",
            "analyse": "Analyse de démonstration.",
            "realisation": "Réalisation de démonstration.",
            "accompagnement": "Accompagnement de démonstration.",
            "restitution": "Restitution de démonstration.",
        },
    }
    sortie = tmp_path / "generation.pptx"

    total = pptx_export.generer_pptx(demande=demande, lignes=lignes,
                                     chemin_sortie=sortie, contenu=contenu)

    assert total == finance.total_mission(lignes)
    assert sortie.exists()

    prs = Presentation(sortie)
    tout_le_texte = " ".join(
        shape.text_frame.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    # Notre propre titre de mission doit être présent, et aucun contenu des
    # exemples de missions clientes réelles du template ne doit avoir fuité.
    assert "Mission de démonstration RFX000TEST" in tout_le_texte
    assert "Fonction Publique" not in tout_le_texte
    # Le contexte rédigé et les 5 phases de la démarche doivent apparaître.
    assert contenu["contexte_redige"] in tout_le_texte
    for phase, texte in contenu["demarche"].items():
        assert texte in tout_le_texte, f"phase {phase} absente du PowerPoint"
    assert "Phase 1 — Cadrage" in tout_le_texte
    assert "Phase 5 — Restitution" in tout_le_texte


@pytest.mark.skipif(
    not config.TEMPLATE_PPTX_PATH.exists(),
    reason="data/template_proposition.pptx est un fichier confidentiel local, absent en CI",
)
def test_generer_pptx_sans_contenu_redige_omet_les_sections(tmp_path) -> None:
    from pptx import Presentation

    demande = {"titre": "Mission sans contenu", "reference": "RFX000VIDE"}
    sortie = tmp_path / "generation_vide.pptx"

    pptx_export.generer_pptx(demande=demande, lignes=[], chemin_sortie=sortie, contenu=None)

    prs = Presentation(sortie)
    tout_le_texte = " ".join(
        shape.text_frame.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    # Sans contenu rédigé, ni la slide contexte ni les slides de phases ne
    # doivent exister ("Compréhension du besoin" reste légitime au sommaire).
    assert "Phase 1 — Cadrage" not in tout_le_texte
    assert "Contexte de la mission" not in tout_le_texte
