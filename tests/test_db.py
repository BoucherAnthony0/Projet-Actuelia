"""Test S1 sans LLM : la base se crée et le CRUD consultants fonctionne."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import init_db, get_connection, repository


def test_schema_et_crud(tmp_path=None):
    init_db()
    con = get_connection()
    n0 = repository.count_consultants(con)
    cid = repository.add_consultant(con, nom="Test", prenom="Jean", seniorite="Senior",
                                    annees_experience=5)
    assert repository.get_consultant(con, cid)["nom"] == "Test"
    assert repository.count_consultants(con) == n0 + 1
    con.close()


if __name__ == "__main__":
    test_schema_et_crud()
    print("test_db OK")
