"""Rédaction LLM : compréhension du besoin, démarche d'intervention, synthèse CV.

Le calcul financier reste 100% déterministe (core/finance.py) : ce module ne
rédige que du texte, jamais des chiffres.
"""
import json
import unicodedata

from . import llm

PHASES_DEMARCHE = ("cadrage", "analyse", "realisation", "accompagnement", "restitution")

DEMARCHE_LABELS = {
    "cadrage": "Cadrage",
    "analyse": "Analyse",
    "realisation": "Réalisation",
    "accompagnement": "Accompagnement",
    "restitution": "Restitution",
}

SYSTEM_REDACTION = (
    "Tu es un consultant senior qui rédige le contenu d'une proposition commerciale "
    "en réponse à un appel d'offres. À partir de l'analyse fournie (contexte, objectifs, "
    "enjeux, livrables, compétences, planning), rédige un JSON structuré avec EXACTEMENT "
    "ces 6 clés, toutes à la racine du JSON (aucune imbrication) : "
    '{"contexte_redige": str, "demarche_cadrage": str, "demarche_analyse": str, '
    '"demarche_realisation": str, "demarche_accompagnement": str, "demarche_restitution": str}. '
    "contexte_redige : un paragraphe DÉVELOPPÉ de compréhension du besoin (6 à 10 phrases) "
    "qui reformule la situation du client, ses objectifs, ses enjeux et ce qui est attendu "
    "du prestataire, sur un ton professionnel et engageant. "
    "demarche_cadrage / demarche_analyse / demarche_realisation / demarche_accompagnement / "
    "demarche_restitution : pour CHACUNE de ces 5 phases, un paragraphe SUBSTANTIEL de 4 à 6 "
    "phrases décrivant concrètement les actions menées, la méthode employée, les points de "
    "vigilance et les livrables produits à cette phase. Sois précis et concret, évite les "
    "généralités creuses. "
    "IMPÉRATIF : les 6 clés doivent TOUTES contenir un paragraphe étoffé et non vide, même si "
    "l'analyse fournie est succincte (déduis alors une démarche plausible et standard du "
    "métier) — ne laisse jamais une clé vide, absente ou réduite à une phrase. "
    "N'invente pas de faits précis (chiffres, noms, dates) absents de l'analyse fournie."
)

SYSTEM_SYNTHESE_CV = (
    "Tu rédiges la synthèse CV d'un consultant pour une proposition commerciale, ciblée "
    "sur le besoin de la mission. Tu dois EXCLUSIVEMENT reformuler et sélectionner des "
    "expériences et compétences présentes dans le CV fourni (cv_complet_json). "
    "N'invente RIEN qui ne soit pas dans le CV : ni expérience, ni compétence, ni client, "
    "ni durée. Si le CV ne contient pas d'expérience pertinente pour un aspect du besoin, "
    "ignore cet aspect plutôt que d'inventer. "
    "synthese : un paragraphe DÉVELOPPÉ de 4 à 7 phrases mettant en valeur, à partir du CV, "
    "le parcours, les domaines d'expertise et les réalisations du consultant en lien avec la "
    "mission — exploite toute la matière pertinente du CV plutôt qu'une phrase minimale. "
    "experiences_retenues : liste des expériences du CV les plus pertinentes, reformulées. "
    "Réponds en JSON : {\"synthese\": str, \"experiences_retenues\": [str]}."
)


# Le LLM gratuit renvoie parfois des clés en variantes (anglais, imbriquées) :
# on rapatrie chaque champ vers sa clé canonique.
_ALIAS_CONTEXTE = ("contexte_redige", "contexte", "comprehension", "comprehension_besoin",
                   "understanding", "context")
_ALIAS_PHASE = {
    "cadrage": ("demarche_cadrage", "cadrage", "framing", "scoping"),
    "analyse": ("demarche_analyse", "analyse", "analysis"),
    "realisation": ("demarche_realisation", "realisation", "réalisation", "execution", "implementation"),
    "accompagnement": ("demarche_accompagnement", "accompagnement", "support", "coaching"),
    "restitution": ("demarche_restitution", "restitution", "delivery", "reporting"),
}
_ALIAS_SYNTHESE = ("synthese", "synthèse", "summary", "resume")
_ALIAS_EXPERIENCES = ("experiences_retenues", "experiences", "expériences", "experiences_selectionnees",
                      "selected_experiences", "experience")


def _normaliser_cle(cle: str) -> str:
    """minuscules + accents retirés : « Démarche_Cadrage » -> « demarche_cadrage »."""
    nfd = unicodedata.normalize("NFD", str(cle))
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower().strip()


def _normaliser_dict(source) -> dict:
    if not isinstance(source, dict):
        return {}
    return {_normaliser_cle(k): v for k, v in source.items()}


def _deballer(resultat: dict) -> dict:
    """Déballe un éventuel enrobage {"proposition": {...}} renvoyé par certains modèles."""
    if isinstance(resultat, dict) and len(resultat) == 1:
        seule = next(iter(resultat.values()))
        if isinstance(seule, dict):
            return seule
    return resultat if isinstance(resultat, dict) else {}


def _premier_present(source: dict, cles: tuple):
    for cle in cles:
        if cle in source and source[cle] not in (None, "", [], {}):
            return source[cle]
    return None


def rediger_contenu(analyse_json: dict, *, retourner_brut: bool = False):
    """Rédige contexte + démarche. Avec retourner_brut=True, renvoie (contenu, réponse_llm_brute)."""
    user = json.dumps(analyse_json or {}, ensure_ascii=False)
    brut = llm.complete_json(SYSTEM_REDACTION, user)
    resultat = _normaliser_dict(_deballer(brut))

    # La démarche peut arriver à plat (demarche_cadrage) ou imbriquée ({"demarche": {"cadrage": ...}}).
    demarche_imbriquee = _normaliser_dict(resultat.get("demarche"))

    def _phase(nom: str) -> str:
        valeur = _premier_present(resultat, _ALIAS_PHASE[nom])
        if not valeur and demarche_imbriquee:
            valeur = _premier_present(demarche_imbriquee, _ALIAS_PHASE[nom] + (nom,))
        return valeur or ""

    contenu = {
        "contexte_redige": _premier_present(resultat, _ALIAS_CONTEXTE) or "",
        "demarche": {phase: _phase(phase) for phase in PHASES_DEMARCHE},
    }
    return (contenu, brut) if retourner_brut else contenu


def synthetiser_cv(cv_complet: dict, analyse_json: dict, *, retourner_brut: bool = False):
    """Synthèse CV ciblée mission. Avec retourner_brut=True, renvoie (résultat, réponse_llm_brute)."""
    user = json.dumps({"cv": cv_complet or {}, "besoin": analyse_json or {}}, ensure_ascii=False)
    brut = llm.complete_json(SYSTEM_SYNTHESE_CV, user)
    resultat = _normaliser_dict(_deballer(brut))

    experiences = _premier_present(resultat, _ALIAS_EXPERIENCES)
    if isinstance(experiences, str):
        experiences = [ligne.strip() for ligne in experiences.splitlines() if ligne.strip()]

    contenu = {
        "synthese": _premier_present(resultat, _ALIAS_SYNTHESE) or "",
        "experiences_retenues": list(experiences or []),
    }
    return (contenu, brut) if retourner_brut else contenu
