"""Génération de la proposition PowerPoint à partir du template Actuelia.

Le fichier de template (data/template_proposition.pptx) contient du contenu
de marque et des exemples de missions clients réels : il est volontairement
hors Git (voir .gitignore et README). Sans lui, la génération est indisponible.

Stratégie : plutôt que reconstruire des slides depuis des mises en page
vides, on duplique des slides réelles du template (structure, images,
mise en forme) puis on ne remplace que le texte/les données nécessaires.
Cela préserve fidèlement la charte graphique. Le calcul financier reste
100% déterministe (core/finance.py) : ce module ne fait que mettre en
forme du texte et des chiffres déjà calculés, jamais de calcul lui-même.
"""
import copy
from datetime import date

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Pt

import config
from . import finance

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Index (base 0) des slides du template réutilisées telles quelles.
_IDX_COUVERTURE = 0
_IDX_SOMMAIRE = 1
_IDX_INTERCALAIRE_CABINET = 2
_IDX_CABINET_DEBUT = 3
_IDX_CABINET_FIN = 8  # inclus
_IDX_INTERCALAIRE_COMMERCIAL = 29
_IDX_BUDGET = 30
_IDX_FIN = 31

_COULEUR_ENTETE = RGBColor(0x44, 0x54, 0x6A)  # dk2 du thème Actuelia

SOMMAIRE_SECTIONS = (
    "Présentation du cabinet",
    "Compréhension du besoin",
    "Notre vision de la mission",
    "Démarche d'intervention",
    "Équipe proposée",
    "Proposition commerciale",
)


def template_disponible() -> bool:
    return config.TEMPLATE_PPTX_PATH.exists()


def _dupliquer_slide(prs: Presentation, index_source: int):
    """Duplique prs.slides[index_source] en fin de présentation (images comprises)."""
    source = prs.slides[index_source]
    dest = prs.slides.add_slide(source.slide_layout)

    for shape in list(dest.shapes):
        shape._element.getparent().remove(shape._element)

    rid_map = {}
    for rid, rel in source.part.rels.items():
        if rel.is_external:
            continue
        rid_map[rid] = dest.part.relate_to(rel.target_part, rel.reltype)

    for shape in source.shapes:
        new_el = copy.deepcopy(shape._element)
        for el in new_el.iter():
            for attr, val in list(el.attrib.items()):
                if attr.startswith("{%s}" % _R_NS) and val in rid_map:
                    el.attrib[attr] = rid_map[val]
        dest.shapes._spTree.append(new_el)

    return dest


def _forme(slide, nom: str):
    for shape in slide.shapes:
        if shape.name == nom:
            return shape
    return None


def _supprimer_forme(slide, nom: str) -> None:
    shape = _forme(slide, nom)
    if shape is not None:
        shape._element.getparent().remove(shape._element)


def _set_placeholder(slide, idx: int, texte: str) -> None:
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == idx:
            shape.text_frame.text = texte or ""
            return
    raise ValueError(f"Placeholder idx={idx} introuvable sur la slide « {slide.slide_layout.name} ».")


def _ouvrir_gabarit() -> Presentation:
    if not template_disponible():
        raise FileNotFoundError(
            "Template PowerPoint introuvable (data/template_proposition.pptx). "
            "C'est un fichier local volontairement hors Git — voir le README."
        )
    return Presentation(config.TEMPLATE_PPTX_PATH)


def _slide_couverture(prs: Presentation, titre_mission: str) -> None:
    slide = _dupliquer_slide(prs, _IDX_COUVERTURE)
    _set_placeholder(slide, 0, f"Réponse à appel d'offres :\n{titre_mission}")
    _set_placeholder(slide, 13, date.today().strftime("%B %Y"))
    _supprimer_forme(slide, "Picture 2")  # logo du client de l'exemple d'origine


def _slide_sommaire(prs: Presentation) -> None:
    _dupliquer_slide(prs, _IDX_SOMMAIRE)
    # Les libellés par défaut du template correspondent déjà aux 6 sections
    # cibles (Présentation du cabinet ... Proposition commerciale) ; rien à
    # changer tant que le contenu généré suit cette même structure.


def _presentation_cabinet(prs: Presentation) -> None:
    for idx in range(_IDX_CABINET_DEBUT, _IDX_CABINET_FIN + 1):
        _dupliquer_slide(prs, idx)
    _dupliquer_slide(prs, _IDX_INTERCALAIRE_CABINET)


def _intercalaire(prs: Presentation, titre: str) -> None:
    slide = _dupliquer_slide(prs, _IDX_INTERCALAIRE_COMMERCIAL)
    _set_placeholder(slide, 0, titre)


def _styler_entete_ligne(ligne, gras: bool, fond: RGBColor | None, couleur_texte: RGBColor | None) -> None:
    for cell in ligne.cells:
        if fond is not None:
            cell.fill.solid()
            cell.fill.fore_color.rgb = fond
        for para in cell.text_frame.paragraphs:
            para.font.bold = gras
            para.font.size = Pt(11)
            if couleur_texte is not None:
                para.font.color.rgb = couleur_texte


def _slide_budget(prs: Presentation, lignes: list) -> float:
    """Ajoute la slide budget. Retourne le total (calculé par core/finance, jamais par le LLM)."""
    slide = _dupliquer_slide(prs, _IDX_BUDGET)
    _set_placeholder(slide, 0, "Proposition commerciale")

    ancienne = _forme(slide, "Tableau 5")
    left, top, width = ancienne.left, ancienne.top, ancienne.width
    hauteur_par_ligne = ancienne.height // len(ancienne.table.rows)
    _supprimer_forme(slide, "Tableau 5")
    _supprimer_forme(slide, "Tableau 8")

    n_lignes = len(lignes) + 2  # entête + une ligne par consultant + total
    hauteur = min(hauteur_par_ligne * n_lignes, prs.slide_height - top - 250000)
    graphic_frame = slide.shapes.add_table(n_lignes, 5, left, top, width, hauteur)
    table = graphic_frame.table

    entetes = ["Consultant", "Grade", "Jours", "TJM appliqué", "Total"]
    for c, texte in enumerate(entetes):
        table.cell(0, c).text = texte
    _styler_entete_ligne(table.rows[0], gras=True, fond=_COULEUR_ENTETE, couleur_texte=RGBColor(0xFF, 0xFF, 0xFF))

    total_mission = finance.total_mission(lignes)
    for r, ligne in enumerate(lignes, start=1):
        total_ligne = finance.total_ligne(ligne["nb_jours"], ligne["tjm_applique"])
        valeurs = [
            f"{ligne['prenom']} {ligne['nom']}",
            ligne["grade"] or ligne["seniorite"] or "",
            f"{ligne['nb_jours']:g}" if ligne["nb_jours"] else "0",
            f"{ligne['tjm_applique']:,.0f} €".replace(",", " ") if ligne["tjm_applique"] else "—",
            f"{total_ligne:,.0f} €".replace(",", " "),
        ]
        for c, texte in enumerate(valeurs):
            table.cell(r, c).text = texte

    ligne_totale = n_lignes - 1
    for c, texte in enumerate(["", "", "", "Total", f"{total_mission:,.0f} €".replace(",", " ")]):
        table.cell(ligne_totale, c).text = texte
    _styler_entete_ligne(table.rows[ligne_totale], gras=True, fond=None, couleur_texte=None)

    return total_mission


def _slide_fin(prs: Presentation) -> None:
    _dupliquer_slide(prs, _IDX_FIN)


def _retirer_slides_modele(prs: Presentation, n: int) -> None:
    """Retire les n premières slides (les exemples du template, contenu client réel)."""
    id_list = prs.slides._sldIdLst
    for sld in list(id_list)[:n]:
        id_list.remove(sld)


def generer_pptx(*, demande: dict, lignes: list, chemin_sortie) -> float:
    """Génère le fichier .pptx sur disque. Retourne le total mission (déterministe)."""
    prs = _ouvrir_gabarit()
    n_slides_modele = len(prs.slides)

    titre_mission = demande["titre"] or demande["reference"] or "Proposition commerciale"
    _slide_couverture(prs, titre_mission)
    _slide_sommaire(prs)
    _presentation_cabinet(prs)
    _intercalaire(prs, "Proposition commerciale")
    total = _slide_budget(prs, lignes)
    _slide_fin(prs)

    _retirer_slides_modele(prs, n_slides_modele)
    prs.save(chemin_sortie)
    return total
