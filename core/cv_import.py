"""Import d'un CV : parsing -> extraction structurée (LLM) -> base."""
from pathlib import Path
from . import parsing, llm
from db import repository

SYSTEM = ('Extrais un profil structuré du CV. JSON : {"nom": str, "prenom": str, '
          '"titre": str, "seniorite": str, "annees_experience": int, '
          '"formation": str, "experiences": [{"client": str, "secteur": str, '
          '"role": str, "description": str}], "competences": [str]}')


def importer_cv(con, chemin: str | Path) -> int:
    texte = parsing.parse_file(chemin)
    profil = llm.complete_json(SYSTEM, texte[:12000])
    return repository.add_consultant(
        con,
        nom=profil.get("nom", ""), prenom=profil.get("prenom", ""),
        titre=profil.get("titre"), seniorite=profil.get("seniorite"),
        annees_experience=profil.get("annees_experience"),
        formation=profil.get("formation"),
        cv_complet_json=profil, chemin_cv_source=str(chemin))
