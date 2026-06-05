"""Application S1 — objectif unique : importer des CV, les structurer, les lister."""
import streamlit as st
import config
from db import init_db, get_connection, repository
from core import cv_import

st.set_page_config(page_title="Actuelia — Import CV (S1)", page_icon="📇", layout="wide")


@st.cache_resource
def _bootstrap():
    return init_db()


_bootstrap()
con = get_connection()

st.title("Import & structuration des CV — Semaine 1")
fournisseur = "Claude" if config.LLM_PROVIDER == "anthropic" else f"gratuit ({config.LLM_MODEL})"
c1, c2 = st.columns(2)
c1.metric("LLM", "configuré" if config.llm_configure() else "non config", fournisseur)
c2.metric("Consultants en base", repository.count_consultants(con))

if not config.llm_configure():
    st.info(" clé du LLM dans `.env` (voir README) pour activer l'extraction.")

st.divider()
st.subheader("Importer des CV (PDF / Word)")
files = st.file_uploader("Déposer un ou plusieurs CV", type=["pdf", "docx", "doc"],
                         accept_multiple_files=True)
if st.button("Importer", disabled=not (files and config.llm_configure())):
    for f in files:
        dest = config.CV_DIR / f.name
        dest.write_bytes(f.getbuffer())
        try:
            cid = cv_import.importer_cv(con, dest)
            st.success(f"Importé : {f.name} (consultant id {cid})")
        except Exception as e:
            st.error(f"{f.name} : {e}")

st.divider()
st.subheader("Consultants en base")
rows = repository.list_consultants(con)
if rows:
    st.dataframe([{"id": r["id"], "nom": r["nom"], "prénom": r["prenom"],
                   "titre": r["titre"], "séniorité": r["seniorite"],
                   "années d'XP": r["annees_experience"]} for r in rows],
                 use_container_width=True)
else:
    st.caption("Aucun consultant importé pour l'instant.")
