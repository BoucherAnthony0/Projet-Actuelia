"""Analyse LLM enrichie d'une demande : contexte, objectifs, enjeux, compétences, planning.

build_request_draft() (core/parsing.py) reste l'extraction rapide par regex
(référence/titre/client/livrables). Cette analyse LLM vient l'enrichir avant
que la rédaction (core/redaction.py) ne s'appuie dessus.
"""
from . import llm

SYSTEM = (
    "Tu es un consultant senior qui prépare une réponse à un appel d'offres. "
    "Analyse le texte brut fourni et restitue un JSON avec EXACTEMENT ces six "
    "clés, en français, orthographiées à l'identique : "
    '{"contexte": str, "objectifs": [str], "enjeux": [str], "livrables": [str], '
    '"competences": [str], "planning": str}. '
    "contexte : un paragraphe synthétisant la situation et la demande du client. "
    "objectifs : ce que le client veut obtenir. "
    "enjeux : les risques et bénéfices en jeu. "
    "livrables : les livrables attendus. "
    "competences : les compétences requises pour la mission. "
    "planning : résumé du calendrier/jalons si mentionné, sinon chaîne vide. "
    "IMPÉRATIF : remplis TOUTES les clés à partir du texte — même si l'appel "
    "d'offres est succinct, déduis un contexte, des objectifs, des enjeux et "
    "des compétences plausibles ; ne laisse une clé vide que si l'information "
    "est réellement absente. N'invente pas de faits (noms, chiffres, dates) "
    "qui ne seraient pas dans le texte."
)

# Le LLM gratuit renvoie parfois des variantes de clés (anglais, singulier,
# accents manquants) ; on les rapatrie vers nos clés canoniques.
_ALIAS = {
    "contexte": ("contexte", "context", "contexte_mission", "comprehension"),
    "objectifs": ("objectifs", "objectif", "objectives", "objective", "buts", "goals"),
    "enjeux": ("enjeux", "enjeu", "stakes", "challenges", "risques"),
    "livrables": ("livrables", "livrable", "deliverables", "deliverable"),
    "competences": ("competences", "compétences", "competence", "skills", "competencies"),
    "planning": ("planning", "calendrier", "timeline", "planning_jalons", "schedule"),
}


def _premier_present(analyse: dict, cles: tuple):
    for cle in cles:
        if cle in analyse and analyse[cle] not in (None, "", [], {}):
            return analyse[cle]
    return None


def analyser_demande(texte_brut: str) -> dict:
    from .redaction import _normaliser_dict  # normalisation partagée (minuscules, sans accents)

    brut = llm.complete_json(SYSTEM, texte_brut[:12000])
    # Tolère un éventuel enrobage {"analyse": {...}} renvoyé par certains modèles.
    if isinstance(brut, dict) and len(brut) == 1:
        seule = next(iter(brut.values()))
        if isinstance(seule, dict):
            brut = seule
    brut = _normaliser_dict(brut)

    def _liste(valeur):
        if isinstance(valeur, str):
            return [ligne.strip() for ligne in valeur.splitlines() if ligne.strip()]
        return list(valeur or [])

    return {
        "contexte": _premier_present(brut, _ALIAS["contexte"]) or "",
        "objectifs": _liste(_premier_present(brut, _ALIAS["objectifs"])),
        "enjeux": _liste(_premier_present(brut, _ALIAS["enjeux"])),
        "livrables": _liste(_premier_present(brut, _ALIAS["livrables"])),
        "competences": _liste(_premier_present(brut, _ALIAS["competences"])),
        "planning": _premier_present(brut, _ALIAS["planning"]) or "",
    }
