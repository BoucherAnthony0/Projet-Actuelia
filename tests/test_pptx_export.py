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
         "titre": "Actuaire Senior", "nb_jours": 20, "tjm_applique": 1370,
         "annees_experience": 8, "formation": "Master Actuariat, ISFA Lyon",
         "synthese_cv": "Synthèse ciblée mission pour Alice.", "photo_path": None,
         "cv_complet_json": '{"competences": ["Solvabilité 2", "Python"], "experiences": []}'},
        {"prenom": "Bob", "nom": "Martin", "grade": "Junior 1 (J1)", "seniorite": None,
         "titre": None, "nb_jours": 15, "tjm_applique": 820,
         "annees_experience": None, "formation": None, "synthese_cv": None, "photo_path": None,
         "cv_complet_json": '{"competences": [], "experiences": [{"client": "MutuelleX", "description": "Reporting QRT"}]}'},
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

    # Fiches CV : une par consultant retenu, avec la synthèse S3 (ou les
    # expériences du CV importé à défaut), sans rien hériter du consultant
    # de l'exemple du template (nom, expertises, photo, logos clients).
    texte_complet = " ".join(
        shape.text_frame.text
        for slide in prs.slides
        for shape in pptx_export._formes(slide)
        if shape.has_text_frame
    )
    tables = " ".join(
        cell.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_table
        for row in shape.table.rows
        for cell in row.cells
    )
    assert "Alice DUPONT" in texte_complet
    assert "Bob MARTIN" in texte_complet
    assert "Synthèse ciblée mission pour Alice." in tables
    assert "MutuelleX — Reporting QRT" in tables
    assert "FITOUCHI" not in texte_complet
    assert "Pilotage des risques santé" not in texte_complet
    slides_cv = [s for s in prs.slides if s.slide_layout.name == "Slide CV"]
    assert len(slides_cv) == 2
    for slide_cv in slides_cv:
        photos = [s for s in slide_cv.shapes if s.shape_type == 13]
        assert photos == [], "photo/logos de l'exemple encore présents sur une fiche CV"


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


@pytest.mark.skipif(
    not config.TEMPLATE_PPTX_PATH.exists(),
    reason="data/template_proposition.pptx est un fichier confidentiel local, absent en CI",
)
def test_generer_pptx_avec_cv_json_corrompu_ne_plante_pas(tmp_path) -> None:
    from pptx import Presentation

    lignes = [{"prenom": "Zoé", "nom": "Faure", "grade": None, "seniorite": "Senior",
               "titre": None, "nb_jours": 5, "tjm_applique": 1000,
               "annees_experience": None, "formation": None, "synthese_cv": None,
               "photo_path": None, "cv_complet_json": "{pas du json"}]
    sortie = tmp_path / "cv_corrompu.pptx"

    pptx_export.generer_pptx(demande={"titre": "T", "reference": "R"},
                             lignes=lignes, chemin_sortie=sortie, contenu=None)

    prs = Presentation(sortie)
    texte = " ".join(s.text_frame.text for sl in prs.slides
                     for s in pptx_export._formes(sl) if s.has_text_frame)
    assert "Zoé FAURE" in texte  # la fiche existe malgré le CV corrompu
