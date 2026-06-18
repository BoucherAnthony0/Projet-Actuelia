import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import get_connection, init_db, repository
from core.parsing import build_request_draft


def test_demande_validation_persists_edited_livrable() -> None:
    init_db()
    con = get_connection()

    raw_text = (
        "RFX008792\n"
        "Client: Actuelia\n"
        "Livrables:\n"
        "- Audit initial\n"
        "- Restitution finale\n"
    )
    draft = build_request_draft(raw_text, "rfx008792.eml")

    client_id = repository.get_or_create_client(con, draft["client_nom"])

    demande_id = repository.create_demande(
        con,
        titre=draft["titre"],
        reference=draft["reference"],
        client_nom=draft["client_nom"],
        client_id=client_id,
        statut="brouillon",
        texte_brut=draft["texte_brut"],
        mode_facturation="regie",
        nb_jours=2.0,
    )

    repository.set_analyse(
        con,
        demande_id,
        {
            **draft["analyse_json"],
            "livrables": ["Audit initial", "Restitution finale corrigée"],
        },
        statut="analyse",
    )

    stored = repository.get_demande(con, demande_id)
    analyse = json.loads(stored["analyse_json"])
    all_demandes = repository.list_demandes(con)

    assert stored["reference"] == "RFX008792"
    assert stored["statut"] == "analyse"
    assert analyse["livrables"][1] == "Restitution finale corrigée"
    assert any(row["id"] == demande_id for row in all_demandes)
    con.close()