import json
import streamlit as st
from db import init_db, get_connection, repository
from core import redaction

st.set_page_config(page_title="Actuelia — Contenu généré", page_icon="✍️", layout="wide")

DEMARCHE_LABELS = {
    "cadrage": "Cadrage",
    "analyse": "Analyse",
    "realisation": "Réalisation",
    "accompagnement": "Accompagnement",
    "restitution": "Restitution",
}


@st.cache_resource
def _bootstrap():
    return init_db()


_bootstrap()
con = get_connection()

st.title("Contenu généré")

demandes = repository.list_demandes(con)
if not demandes:
    st.warning("Aucune demande enregistrée. Déposez et validez une demande depuis l'accueil.")
    st.stop()

labels = {
    f"{d['reference'] or '(sans réf.)'} — {d['titre'] or ''} ({d['client_nom'] or 'client ?'})": d["id"]
    for d in demandes
}
default_id = st.session_state.get("demande_active_id", demandes[0]["id"])
default_index = next((i for i, d in enumerate(demandes) if d["id"] == default_id), 0)

choice = st.selectbox("Demande active", list(labels.keys()), index=default_index)
demande_id = labels[choice]
st.session_state["demande_active_id"] = demande_id

demande = repository.get_demande(con, demande_id)
analyse_json = json.loads(demande["analyse_json"]) if demande["analyse_json"] else {}
contenu = json.loads(demande["contenu_genere_json"]) if demande["contenu_genere_json"] else {}

st.divider()
st.subheader("Contexte & démarche d'intervention")

if st.button("Générer le contenu (LLM)"):
    try:
        contenu = redaction.rediger_contenu(analyse_json)
        st.success("Contenu généré : relisez et corrigez avant enregistrement.")
    except Exception as e:
        st.error(f"Génération impossible : {e}")

contexte_redige = st.text_area(
    "Compréhension du besoin (contexte rédigé)",
    value=contenu.get("contexte_redige", ""),
    height=180,
)

demarche_existante = contenu.get("demarche", {})
demarche_edit = {}
for phase, label in DEMARCHE_LABELS.items():
    demarche_edit[phase] = st.text_area(
        f"Démarche — {label}",
        value=demarche_existante.get(phase, ""),
        height=100,
        key=f"demarche_{phase}",
    )

if st.button("Enregistrer le contenu"):
    repository.set_contenu_genere(con, demande_id, {
        "contexte_redige": contexte_redige,
        "demarche": demarche_edit,
    })
    st.success("Contenu enregistré.")

st.divider()
st.subheader("Synthèse CV par consultant retenu")

lignes = repository.list_lignes(con, demande_id)
if not lignes:
    st.caption("Aucun consultant retenu. Sélectionnez-en depuis l'écran Consultants & Budget.")
else:
    for ligne in lignes:
        st.markdown(f"**{ligne['prenom']} {ligne['nom']}**")
        cid = ligne["consultant_id"]

        if st.button(f"Générer la synthèse CV — {ligne['prenom']} {ligne['nom']}", key=f"gen_synthese_{cid}"):
            consultant = repository.get_consultant(con, cid)
            cv_complet = json.loads(consultant["cv_complet_json"]) if consultant["cv_complet_json"] else {}
            try:
                resultat = redaction.synthetiser_cv(cv_complet, analyse_json)
                st.session_state[f"synthese_texte_{cid}"] = resultat["synthese"]
                st.success("Synthèse générée : relisez avant enregistrement.")
            except Exception as e:
                st.error(f"Génération impossible : {e}")

        valeur_defaut = st.session_state.get(f"synthese_texte_{cid}", ligne["synthese_cv"] or "")
        synthese_texte = st.text_area("Synthèse", value=valeur_defaut, height=150, key=f"synthese_area_{cid}")

        if st.button("Enregistrer la synthèse", key=f"save_synthese_{cid}"):
            repository.set_ligne(con, demande_id, cid, synthese_cv=synthese_texte)
            st.success("Synthèse enregistrée.")
        st.divider()
