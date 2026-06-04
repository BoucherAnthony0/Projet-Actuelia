"""Import en masse des CV depuis une COPIE LOCALE d'un dossier.

    python ingest_cv.py --cv "C:\\copie\\locale\\CV"

Incrémental : chaque fichier est haché, les déjà-traités sont ignorés.
"""
import argparse
import hashlib
from pathlib import Path

import config
from db import get_connection, init_db
from core import cv_import

CV_EXT = {".pdf", ".docx", ".doc"}


def _ensure_tracking(con):
    con.execute("""CREATE TABLE IF NOT EXISTS documents_sources (
        hash TEXT PRIMARY KEY, chemin TEXT, type TEXT,
        ref_id INTEGER, date_indexation TEXT NOT NULL DEFAULT (datetime('now')))""")
    con.commit()


def _hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Import en masse des CV (hors-ligne).")
    ap.add_argument("--cv", required=True, help="Dossier local contenant les CV")
    args = ap.parse_args()

    init_db()
    con = get_connection()
    _ensure_tracking(con)

    fichiers = [p for p in Path(args.cv).rglob("*") if p.suffix.lower() in CV_EXT]
    nouveaux = ignores = erreurs = 0
    for p in fichiers:
        h = _hash(p)
        if con.execute("SELECT 1 FROM documents_sources WHERE hash=?", (h,)).fetchone():
            ignores += 1; continue
        try:
            cid = cv_import.importer_cv(con, p)
            con.execute("INSERT INTO documents_sources(hash,chemin,type,ref_id) VALUES(?,?,?,?)",
                        (h, str(p), "cv", cid)); con.commit()
            nouveaux += 1
            print(f"  + {p.name}  (id {cid})")
        except Exception as e:
            erreurs += 1
            print(f"  ! {p.name} : {e}")
    print(f"\n=> {nouveaux} nouveaux, {ignores} déjà connus, {erreurs} en erreur")
    con.close()


if __name__ == "__main__":
    main()
