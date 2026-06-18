import streamlit as st
import json
import importlib
import config
from db import init_db, get_connection, repository
from core import cv_import, parsing

parsing = importlib.reload(parsing)

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
    st.info("Renseignez la clé du LLM dans `.env` (voir README) pour activer l'extraction.")

st.divider()
st.subheader("Importer des CV (PDF / Word)")
files = st.file_uploader("Déposer un ou plusieurs CV", type=["pdf", "docx", "doc"],
                         accept_multiple_files=True)
if st.button("Importer", disabled=not config.llm_configure()):
    if not files:
        st.warning("Déposez d'abord un ou plusieurs CV avant d'importer.")
    else:
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

st.divider()
st.subheader("Parsing des demandes")
request_file = st.file_uploader(
    "Déposer une demande (.pdf, .docx, .doc, .txt, .md, .eml, .msg)",
    type=["pdf", "docx", "doc", "txt", "md", "eml", "msg"],
    key="request_file",
)
request_text = st.text_area(
    "Ou coller le texte brut",
    height=220,
    key="request_text",
)

def _request_raw_text() -> tuple[str, str]:
    if request_file is not None:
        dest = config.UPLOADS_DIR / request_file.name
        dest.write_bytes(request_file.getbuffer())
        return parsing.parse_file(dest), request_file.name
    if request_text.strip():
        return parsing.parse_text(request_text), "texte collé"
    return "", ""


if st.button("Analyser"):
    raw_text, source_name = _request_raw_text()
    if not raw_text:
        st.warning("Déposez un fichier ou collez un texte avant de lancer l'analyse.")
    else:
        st.session_state.request_draft = parsing.build_request_draft(raw_text, source_name)
        st.session_state.request_draft["demande_id"] = st.session_state.request_draft.get("demande_id")

draft = st.session_state.get("request_draft")
if draft:
    st.caption("Fiche de demande éditable avant enregistrement")
    with st.form("request_validation_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        reference = c1.text_input("Référence", value=draft.get("reference", ""))
        titre = c2.text_input("Titre", value=draft.get("titre", ""))
        client_nom = c1.text_input("Client", value=draft.get("client_nom", ""))
        mode_facturation = c2.selectbox(
            "Mode de facturation",
            ["", "regie", "forfait"],
            index=["", "regie", "forfait"].index(draft.get("mode_facturation", ""))
            if draft.get("mode_facturation", "") in ["", "regie", "forfait"] else 0,
        )
        nb_jours = c1.number_input(
            "Nb jours (indicatif)",
            min_value=0.0,
            step=0.5,
            value=float(draft.get("nb_jours") or 0.0),
        )
        statut = c2.selectbox(
            "Statut",
            ["brouillon", "analyse", "en_cours"],
            index=["brouillon", "analyse", "en_cours"].index(draft.get("statut", "brouillon"))
            if draft.get("statut", "brouillon") in ["brouillon", "analyse", "en_cours"] else 0,
        )
        texte_brut = st.text_area(
            "Texte brut extrait",
            value=draft.get("texte_brut", ""),
            height=260,
        )
        analyse = draft.get("analyse_json", {}) or {}
        livrables_text = st.text_area(
            "Livrables (une ligne par livrable)",
            value="\n".join(analyse.get("livrables", [])),
            height=200,
        )
        submitted = st.form_submit_button("Valider et enregistrer")

    if submitted:
        livrables = [line.strip() for line in livrables_text.splitlines() if line.strip()]
        analyse_json = {
            **analyse,
            "livrables": livrables,
            "source": draft.get("source_name", ""),
        }
        payload = {
            "titre": titre,
            "reference": reference,
            "client_nom": client_nom,
            "statut": statut,
            "texte_brut": texte_brut,
            "mode_facturation": mode_facturation or None,
            "nb_jours": nb_jours,
        }
        demande_id = draft.get("demande_id")
        if demande_id:
            repository.update_demande(con, demande_id, **payload)
            repository.set_analyse(con, demande_id, analyse_json, statut=statut)
        else:
            client_id = repository.get_or_create_client(con, client_nom)
            demande_id = repository.create_demande(
                con,
                **payload,
                client_id=client_id,
            )
            repository.set_analyse(con, demande_id, analyse_json, statut=statut)
        st.session_state.request_draft = {
            **draft,
            **payload,
            "demande_id": demande_id,
            "analyse_json": analyse_json,
        }
        stored = repository.get_demande(con, demande_id)
        st.success(f"Demande enregistrée (id {demande_id})")
        st.json({
            "reference": stored["reference"],
            "titre": stored["titre"],
            "client_nom": stored["client_nom"],
            "statut": stored["statut"],
            "analyse_json": json.loads(stored["analyse_json"]) if stored["analyse_json"] else {},
        })

st.divider()
st.subheader("Demandes enregistrées")
demandes = repository.list_demandes(con)
if demandes:
    st.dataframe(
        [{
            "id": d["id"],
            "référence": d["reference"],
            "titre": d["titre"],
            "client": d["client_nom"],
            "statut": d["statut"],
            "date": d["date_depot"],
        } for d in demandes],
        use_container_width=True,
    )
else:
    st.caption("Aucune demande enregistrée pour l'instant.")
