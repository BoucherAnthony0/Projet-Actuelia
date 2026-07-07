import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import get_connection, init_db, repository


def test_selection_lie_les_consultants_a_la_demande() -> None:
    init_db()
    con = get_connection()

    demande_id = repository.create_demande(
        con, titre="Mission test", reference="RFX000TEST",
        client_nom="Client Test", statut="analyse",
    )
    c1 = repository.add_consultant(con, nom="Dupont", prenom="Alice", seniorite="Senior")
    c2 = repository.add_consultant(con, nom="Martin", prenom="Bob", seniorite="Junior")
    c3 = repository.add_consultant(con, nom="Durand", prenom="Chloé", seniorite="Senior")

    repository.set_ligne(con, demande_id, c1, grade="Senior")
    repository.set_ligne(con, demande_id, c2, grade="Junior")

    lignes = repository.list_lignes(con, demande_id)
    lies = {row["consultant_id"] for row in lignes}

    assert lies == {c1, c2}
    assert c3 not in lies

    repository.remove_ligne(con, demande_id, c2)
    lignes = repository.list_lignes(con, demande_id)
    assert {row["consultant_id"] for row in lignes} == {c1}

    con.close()
