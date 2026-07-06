import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import finance
from db import get_connection, init_db, repository
from db.seed import seed_grilles


def test_total_ligne_et_mission_sont_pures() -> None:
    assert finance.total_ligne(40, 1100) == 44000
    assert finance.total_ligne(0, 1100) == 0.0
    assert finance.total_ligne(10, None) == 0.0

    lignes = [
        {"nb_jours": 40, "tjm_applique": 1100},
        {"nb_jours": 20, "tjm_applique": 1200},
    ]
    assert finance.total_mission(lignes) == 68000


def test_recette_budget_par_lignes_et_grille_reference() -> None:
    init_db()
    con = get_connection()
    seed_grilles(con)
    n_avant = con.execute("SELECT COUNT(*) FROM grilles_tarifaires").fetchone()[0]
    seed_grilles(con)  # ré-exécution : doit rester idempotent
    n_apres = con.execute("SELECT COUNT(*) FROM grilles_tarifaires").fetchone()[0]
    assert n_avant == n_apres

    demande_id = repository.create_demande(
        con, titre="Mission recette", reference="RFX008792",
        client_nom="Client Recette", statut="analyse", mode_facturation="regie",
    )
    c1 = repository.add_consultant(con, nom="Dupont", prenom="Alice", seniorite="Senior")
    c2 = repository.add_consultant(con, nom="Martin", prenom="Bob", seniorite="Expert")

    repository.set_ligne(con, demande_id, c1, grade="Senior", nb_jours=40, tjm_applique=1100)
    repository.set_ligne(con, demande_id, c2, grade="Expert", nb_jours=20, tjm_applique=1200)

    lignes = repository.list_lignes(con, demande_id)
    assert finance.total_mission(lignes) == 68000

    grille = repository.list_grille(con, "regie")
    assert any(row["profil_seniorite"] == "Senior" for row in grille)
    assert repository.tjm_reference(con, "regie", "Senior") == 1100.0

    con.close()
