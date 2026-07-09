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
    sortie = tmp_path / "generation.pptx"

    total = pptx_export.generer_pptx(demande=demande, lignes=lignes, chemin_sortie=sortie)

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
