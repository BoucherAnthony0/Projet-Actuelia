"""Analyse LLM enrichie d'une demande : contexte, objectifs, enjeux, compétences, planning.

build_request_draft() (core/parsing.py) reste l'extraction rapide par regex
(référence/titre/client/livrables). Cette analyse LLM vient l'enrichir avant
que la rédaction (core/redaction.py) ne s'appuie dessus.
"""
from . import llm

SYSTEM = (
    "Tu es un consultant senior qui prépare une réponse à un appel d'offres. "
    "Analyse le texte brut fourni et restitue un JSON structuré : "
    '{"contexte": str, "objectifs": [str], "enjeux": [str], "livrables": [str], '
    '"competences": [str], "planning": str}. '
    "contexte : synthèse de la situation et de la demande du client. "
    "objectifs, enjeux, livrables, competences : listes concises et concrètes. "
    "planning : résumé du calendrier/jalons si mentionné, sinon chaîne vide. "
    "Base-toi uniquement sur les informations présentes dans le texte, sans inventer."
)


def analyser_demande(texte_brut: str) -> dict:
    analyse = llm.complete_json(SYSTEM, texte_brut[:12000])
    return {
        "contexte": analyse.get("contexte") or "",
        "objectifs": list(analyse.get("objectifs") or []),
        "enjeux": list(analyse.get("enjeux") or []),
        "livrables": list(analyse.get("livrables") or []),
        "competences": list(analyse.get("competences") or []),
        "planning": analyse.get("planning") or "",
    }
