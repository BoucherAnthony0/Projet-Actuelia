"""Rédaction LLM : compréhension du besoin, démarche d'intervention, synthèse CV.

Le calcul financier reste 100% déterministe (core/finance.py) : ce module ne
rédige que du texte, jamais des chiffres.
"""
import json
from . import llm

PHASES_DEMARCHE = ("cadrage", "analyse", "realisation", "accompagnement", "restitution")

SYSTEM_REDACTION = (
    "Tu es un consultant senior qui rédige le contenu d'une proposition commerciale "
    "en réponse à un appel d'offres. À partir de l'analyse fournie (contexte, objectifs, "
    "enjeux, livrables, compétences, planning), rédige un JSON structuré : "
    '{"contexte_redige": str, "demarche": {"cadrage": str, "analyse": str, '
    '"realisation": str, "accompagnement": str, "restitution": str}}. '
    "contexte_redige : paragraphe de compréhension du besoin, professionnel et concis. "
    "demarche : une phrase ou un court paragraphe par phase, décrivant concrètement "
    "les actions menées. N'invente pas d'information absente de l'analyse fournie."
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
    demarche_brute = resultat.get("demarche") or {}
    return {
        "contexte_redige": resultat.get("contexte_redige") or "",
        "demarche": {phase: demarche_brute.get(phase, "") for phase in PHASES_DEMARCHE},
    }


def synthetiser_cv(cv_complet: dict, analyse_json: dict) -> dict:
    user = json.dumps({"cv": cv_complet or {}, "besoin": analyse_json or {}}, ensure_ascii=False)
    resultat = llm.complete_json(SYSTEM_SYNTHESE_CV, user)
    return {
        "synthese": resultat.get("synthese") or "",
        "experiences_retenues": list(resultat.get("experiences_retenues") or []),
    }
