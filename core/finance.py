"""Calcul financier de la proposition — 100% déterministe, jamais confié au LLM."""


def total_ligne(nb_jours, tjm_applique) -> float:
    if not nb_jours or not tjm_applique:
        return 0.0
    return round(float(nb_jours) * float(tjm_applique), 2)


def total_mission(lignes) -> float:
    return round(sum(total_ligne(ligne["nb_jours"], ligne["tjm_applique"]) for ligne in lignes), 2)
