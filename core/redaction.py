"""Rédaction LLM : compréhension du besoin, démarche d'intervention, synthèse CV.

Le calcul financier reste 100% déterministe (core/finance.py) : ce module ne
rédige que du texte, jamais des chiffres.
"""
import json
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
    "contexte_redige : paragraphe de compréhension du besoin, professionnel et concis. "
    "demarche_cadrage / demarche_analyse / demarche_realisation / demarche_accompagnement / "
    "demarche_restitution : pour CHACUNE de ces 5 phases, un paragraphe concret décrivant "
    "les actions menées sur cette mission. "
    "IMPÉRATIF : les 6 clés doivent TOUTES contenir du texte non vide, même générique si "
    "l'analyse fournie est succincte — ne laisse jamais une clé vide ou absente. "
    "N'invente pas d'information absente de l'analyse fournie."
)

SYSTEM_SYNTHESE_CV = (
    "Tu rédiges la synthèse CV d'un consultant pour une proposition commerciale, ciblée "
    "sur le besoin de la mission. Tu dois EXCLUSIVEMENT reformuler et sélectionner des "
    "expériences et compétences présentes dans le CV fourni (cv_complet_json). "
    "N'invente RIEN qui ne soit pas dans le CV : ni expérience, ni compétence, ni client, "
    "ni durée. Si le CV ne contient pas d'expérience pertinente pour un aspect du besoin, "
    "ignore cet aspect plutôt que d'inventer. Réponds en JSON : "
    '{"synthese": str, "experiences_retenues": [str]}.'
)


def rediger_contenu(analyse_json: dict) -> dict:
    user = json.dumps(analyse_json or {}, ensure_ascii=False)
    resultat = llm.complete_json(SYSTEM_REDACTION, user)
    return {
        "contexte_redige": resultat.get("contexte_redige") or "",
        "demarche": {phase: resultat.get(f"demarche_{phase}") or "" for phase in PHASES_DEMARCHE},
    }


def synthetiser_cv(cv_complet: dict, analyse_json: dict) -> dict:
    user = json.dumps({"cv": cv_complet or {}, "besoin": analyse_json or {}}, ensure_ascii=False)
    resultat = llm.complete_json(SYSTEM_SYNTHESE_CV, user)
    return {
        "synthese": resultat.get("synthese") or "",
        "experiences_retenues": list(resultat.get("experiences_retenues") or []),
    }
