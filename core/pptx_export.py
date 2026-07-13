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
import json
from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

import config
from . import finance
from .redaction import DEMARCHE_LABELS

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Index (base 0) des slides du template réutilisées telles quelles.
_IDX_COUVERTURE = 0
_IDX_SOMMAIRE = 1
_IDX_INTERCALAIRE_CABINET = 2
_IDX_CABINET_DEBUT = 3
_IDX_CABINET_FIN = 8  # inclus
_IDX_SLIDE_TEXTE = 10  # slide texte "propre" : titre + sous-titre + corps
_IDX_CV = 24  # slide CV la plus complète (photo, formation, expériences, compétences)
_IDX_INTERCALAIRE_COMMERCIAL = 29
_IDX_BUDGET = 30
_IDX_FIN = 31

# Sur la slide CV du template, les pictos à droite de cette limite sont les
# logos des clients du consultant de l'exemple : sans équivalent en base,
# ils sont retirés pour ne pas attribuer ces références à un autre profil.
_CV_LIMITE_LOGOS = Emu(8686800)  # ~9,5 pouces

_COULEUR_ENTETE = RGBColor(0x44, 0x54, 0x6A)  # dk2 du thème Actuelia

_MOIS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre")

# Libellés du sommaire : placeholder idx -> texte. Le 6e item du sommaire du
# template est une zone de texte libre (pas un placeholder), gérée à part.
_SOMMAIRE_PLACEHOLDERS = {
    13: "Présentation du cabinet",
    17: "Compréhension du besoin",
    18: "Démarche d'intervention",
    19: "Équipe proposée",
    20: "Proposition commerciale",
}


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


def _formes(conteneur):
    """Itère récursivement toutes les formes, y compris à l'intérieur des groupes."""
    for shape in conteneur.shapes:
        yield shape
        if shape.shape_type == 6:  # GROUP
            yield from _formes(shape)


def _forme(slide, nom: str, *, recursif: bool = False):
    for shape in (_formes(slide) if recursif else slide.shapes):
        if shape.name == nom:
            return shape
    return None


def _remplacer_texte(text_frame, lignes: list[str] | str) -> None:
    """Remplace le texte en conservant la mise en forme du 1er run existant.

    Assigner .text directement effacerait la mise en forme locale (couleur,
    gras, taille) des zones de texte libres et des cellules de tableau.
    """
    if isinstance(lignes, str):
        lignes = lignes.split("\n")
    lignes = lignes or [""]

    for para in list(text_frame.paragraphs[1:]):
        para._p.getparent().remove(para._p)

    def _ecrire(paragraphe, texte: str) -> None:
        if paragraphe.runs:
            paragraphe.runs[0].text = texte
            for run in paragraphe.runs[1:]:
                run._r.getparent().remove(run._r)
        else:
            paragraphe.text = texte

    premier = text_frame.paragraphs[0]
    _ecrire(premier, lignes[0])

    corps = premier._p.getparent()
    for ligne in lignes[1:]:
        corps.append(copy.deepcopy(premier._p))
        _ecrire(text_frame.paragraphs[-1], ligne)


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
    aujourd_hui = date.today()
    _set_placeholder(slide, 13, f"{_MOIS_FR[aujourd_hui.month - 1].capitalize()} {aujourd_hui.year}")
    _supprimer_forme(slide, "Picture 2")  # logo du client de l'exemple d'origine


def _slide_sommaire(prs: Presentation) -> None:
    slide = _dupliquer_slide(prs, _IDX_SOMMAIRE)
    for idx, texte in _SOMMAIRE_PLACEHOLDERS.items():
        _set_placeholder(slide, idx, texte)
    # Le 6e item du sommaire du template est une zone de texte libre héritée
    # de l'exemple ("Proposition commerciale") : nos sections tiennent en 5
    # entrées, on la retire pour ne pas afficher un doublon.
    for shape in list(slide.shapes):
        if not shape.is_placeholder and shape.has_text_frame \
                and "Proposition commerciale" in shape.text_frame.text:
            shape._element.getparent().remove(shape._element)


def _presentation_cabinet(prs: Presentation) -> None:
    _dupliquer_slide(prs, _IDX_INTERCALAIRE_CABINET)
    for idx in range(_IDX_CABINET_DEBUT, _IDX_CABINET_FIN + 1):
        _dupliquer_slide(prs, idx)


def _intercalaire(prs: Presentation, titre: str) -> None:
    slide = _dupliquer_slide(prs, _IDX_INTERCALAIRE_COMMERCIAL)
    _set_placeholder(slide, 0, titre)


def _slide_texte(prs: Presentation, titre: str, sous_titre: str, corps: str) -> None:
    """Slide de contenu texte au gabarit du template (titre de section + sous-titre + corps)."""
    slide = _dupliquer_slide(prs, _IDX_SLIDE_TEXTE)
    _set_placeholder(slide, 0, titre)
    _set_placeholder(slide, 13, sous_titre)
    _set_placeholder(slide, 1, corps)


def _section_contexte(prs: Presentation, contenu: dict) -> None:
    contexte = (contenu or {}).get("contexte_redige", "").strip()
    if not contexte:
        return
    _intercalaire(prs, "Compréhension du besoin")
    _slide_texte(prs, "Compréhension du besoin", "Contexte de la mission", contexte)


def _section_demarche(prs: Presentation, contenu: dict) -> None:
    demarche = (contenu or {}).get("demarche", {}) or {}
    phases = [(phase, label) for phase, label in DEMARCHE_LABELS.items()
              if (demarche.get(phase) or "").strip()]
    if not phases:
        return
    _intercalaire(prs, "Démarche d'intervention")
    for numero, (phase, label) in enumerate(phases, start=1):
        _slide_texte(prs, "Démarche d'intervention",
                     f"Phase {numero} — {label}", demarche[phase].strip())


def _val(ligne, cle: str):
    """Accès tolérant (sqlite3.Row ou dict) : None si la colonne n'existe pas."""
    try:
        return ligne[cle]
    except (KeyError, IndexError):
        return None


def _slide_cv(prs: Presentation, ligne) -> None:
    """Fiche CV d'un consultant, clonée depuis la slide CV du template.

    Tout ce qui est propre au consultant de l'exemple (photo, logos de ses
    clients, intitulés d'expertise) est remplacé ou retiré : rien de son
    profil ne doit être attribué à un autre consultant.
    """
    slide = _dupliquer_slide(prs, _IDX_CV)

    nom_complet = f"{_val(ligne, 'prenom') or ''} {(_val(ligne, 'nom') or '').upper()}".strip()
    _set_placeholder(slide, 0, nom_complet)

    sous_titre = []
    if _val(ligne, "annees_experience"):
        sous_titre.append(f"{ligne['annees_experience']} années d'expérience")
    if _val(ligne, "titre"):
        sous_titre.append(ligne["titre"])
    grade = _val(ligne, "grade") or _val(ligne, "seniorite")
    if grade and grade not in sous_titre:
        sous_titre.append(grade)
    _set_placeholder(slide, 11, "\n".join(sous_titre) or nom_complet)

    cv_brut = _val(ligne, "cv_complet_json")
    cv = json.loads(cv_brut) if isinstance(cv_brut, str) and cv_brut else (cv_brut or {})

    formation = _val(ligne, "formation") or cv.get("formation") or ""
    _remplacer_texte(_forme(slide, "ZoneTexte 10").text_frame, formation)

    # Bandeaux d'expertise de l'exemple -> intitulés génériques.
    _remplacer_texte(_forme(slide, "ZoneTexte 13", recursif=True).text_frame, "Expériences significatives")
    _remplacer_texte(_forme(slide, "ZoneTexte 21", recursif=True).text_frame, "Compétences clés")

    # Expériences : la synthèse ciblée mission (S3) en priorité, sinon les
    # expériences brutes du CV importé.
    synthese = (_val(ligne, "synthese_cv") or "").strip()
    if not synthese:
        synthese = "\n".join(
            f"{exp.get('client', '')} — {exp.get('description', '')}".strip(" —")
            for exp in cv.get("experiences", [])[:4]
        )
    _remplacer_texte(_forme(slide, "Tableau 3").table.cell(0, 0).text_frame, synthese)

    # Compétences : réparties sur les 3 zones du bas (2 par zone, comme le modèle).
    competences = [c for c in cv.get("competences", []) if isinstance(c, str)][:6]
    for i, nom_zone in enumerate(("ZoneTexte 50", "ZoneTexte 51", "ZoneTexte 52")):
        _remplacer_texte(_forme(slide, nom_zone).text_frame, competences[i * 2:i * 2 + 2] or [""])

    # Photo : celle du consultant si disponible, sinon on retire celle de l'exemple.
    photo = _forme(slide, "object 19")
    photo_path = _val(ligne, "photo_path")
    if photo is not None:
        if photo_path and Path(photo_path).exists():
            left, top, width, height = photo.left, photo.top, photo.width, photo.height
            photo._element.getparent().remove(photo._element)
            slide.shapes.add_picture(photo_path, left, top, width, height)
        else:
            photo._element.getparent().remove(photo._element)

    # Logos des clients de l'exemple (colonne de droite) : retirés.
    for shape in list(slide.shapes):
        if shape.shape_type == 13 and shape.left and shape.left > _CV_LIMITE_LOGOS:  # PICTURE
            shape._element.getparent().remove(shape._element)


def _section_equipe(prs: Presentation, lignes: list) -> None:
    if not lignes:
        return
    _intercalaire(prs, "Équipe proposée")
    for ligne in lignes:
        _slide_cv(prs, ligne)


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
    total_jours = sum(float(ligne["nb_jours"] or 0) for ligne in lignes)
    _set_placeholder(
        slide, 1,
        "Le tableau ci-dessous récapitule le budget évalué pour la mission, "
        f"sur une base de {total_jours:g} jours et des profils mobilisés :",
    )

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


def generer_pptx(*, demande: dict, lignes: list, chemin_sortie, contenu: dict | None = None) -> float:
    """Génère le fichier .pptx sur disque. Retourne le total mission (déterministe).

    contenu = contenu_genere_json de la demande (contexte rédigé + démarche S3) ;
    les sections correspondantes sont simplement omises s'il est absent ou vide.
    """
    prs = _ouvrir_gabarit()
    n_slides_modele = len(prs.slides)

    titre_mission = demande["titre"] or demande["reference"] or "Proposition commerciale"
    _slide_couverture(prs, titre_mission)
    _slide_sommaire(prs)
    _presentation_cabinet(prs)
    _section_contexte(prs, contenu)
    _section_demarche(prs, contenu)
    _section_equipe(prs, lignes)
    _intercalaire(prs, "Proposition commerciale")
    total = _slide_budget(prs, lignes)
    _slide_fin(prs)

    _retirer_slides_modele(prs, n_slides_modele)
    prs.save(chemin_sortie)
    return total
