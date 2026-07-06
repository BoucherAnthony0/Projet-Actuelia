import streamlit as st
from db import init_db, get_connection, repository

st.set_page_config(page_title="Actuelia — Consultants & Budget", page_icon="🧮", layout="wide")


@st.cache_resource
def _bootstrap():
    return init_db()


_bootstrap()
con = get_connection()

st.title("Consultants & Budget")

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

st.divider()
st.subheader("Paramètres de la mission")
c1, c2 = st.columns(2)
mode_options = ["", "regie", "forfait"]
mode_index = mode_options.index(demande["mode_facturation"]) if demande["mode_facturation"] in mode_options else 0
mode_facturation = c1.selectbox("Mode de facturation", mode_options, index=mode_index)
client_nom = c2.text_input("Client", value=demande["client_nom"] or "")

if st.button("Enregistrer les paramètres de mission"):
    client_id = repository.get_or_create_client(con, client_nom) if client_nom.strip() else demande["client_id"]
    repository.update_demande(
        con, demande_id,
        mode_facturation=mode_facturation or None,
        client_nom=client_nom or None,
        client_id=client_id,
    )
    st.success("Paramètres mis à jour.")
    demande = repository.get_demande(con, demande_id)

st.divider()
st.subheader("Sélection des consultants")

consultants = repository.list_consultants(con)
lignes_existantes = {row["consultant_id"]: row for row in repository.list_lignes(con, demande_id)}

if not consultants:
    st.caption("Aucun consultant en base. Importez des CV depuis l'accueil.")
else:
    with st.form("selection_consultants_form"):
        cases = {}
        for cons in consultants:
            label = f"{cons['prenom']} {cons['nom']} — {cons['titre'] or cons['seniorite'] or ''}"
            cases[cons["id"]] = st.checkbox(
                label, value=cons["id"] in lignes_existantes, key=f"select_{cons['id']}"
            )
        submitted = st.form_submit_button("Mettre à jour la sélection")

    if submitted:
        for consultant_id, checked in cases.items():
            deja_lie = consultant_id in lignes_existantes
            if checked and not deja_lie:
                repository.set_ligne(con, demande_id, consultant_id)
            elif not checked and deja_lie:
                repository.remove_ligne(con, demande_id, consultant_id)
        st.success("Sélection mise à jour.")
        lignes_existantes = {row["consultant_id"]: row for row in repository.list_lignes(con, demande_id)}

st.divider()
st.subheader("Consultants retenus pour cette demande")
lignes = repository.list_lignes(con, demande_id)
if lignes:
    st.dataframe([{
        "consultant": f"{row['prenom']} {row['nom']}",
        "grade": row["grade"],
        "jours": row["nb_jours"],
        "tjm référence": row["tjm_reference"],
        "tjm appliqué": row["tjm_applique"],
    } for row in lignes], use_container_width=True)
else:
    st.caption("Aucun consultant retenu pour l'instant.")
