import streamlit as st
from db import init_db, get_connection, repository
from core import finance

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
st.subheader("Tableau financier")

mode_grille = mode_facturation or demande["mode_facturation"] or "regie"
grille = repository.list_grille(con, mode_grille, demande["client_id"])
profils_grille = sorted({row["profil_seniorite"] for row in grille if row["profil_seniorite"]})

lignes = repository.list_lignes(con, demande_id)
if not lignes:
    st.caption("Sélectionnez au moins un consultant ci-dessus pour construire le budget.")
else:
    col_grille, col_lignes = st.columns([1, 2])

    with col_grille:
        st.caption(f"Grille tarifaire de référence ({mode_grille})")
        if grille:
            st.dataframe([{
                "profil": row["profil_seniorite"],
                "tjm": row["tjm"],
                "portée": "client" if row["client_id"] else "générique",
            } for row in grille], use_container_width=True, hide_index=True)
        else:
            st.caption("Aucune grille tarifaire pour ce mode de facturation.")

    with col_lignes:
        saisie = {}
        for ligne in lignes:
            st.markdown(f"**{ligne['prenom']} {ligne['nom']}**")
            c1, c2, c3 = st.columns(3)
            options = profils_grille or [ligne["grade"] or ligne["seniorite"] or ""]
            default_grade = ligne["grade"] or ligne["seniorite"]
            grade_index = options.index(default_grade) if default_grade in options else 0
            grade = c1.selectbox("Grade", options, index=grade_index, key=f"grade_{ligne['consultant_id']}")
            nb_jours = c2.number_input(
                "Jours", min_value=0.0, step=0.5,
                value=float(ligne["nb_jours"] or 0), key=f"jours_{ligne['consultant_id']}",
            )
            tjm_ref = repository.tjm_reference(con, mode_grille, grade, demande["client_id"])
            c3.metric("TJM référence", f"{tjm_ref:.0f} €" if tjm_ref else "—")
            tjm_applique = st.number_input(
                "TJM appliqué", min_value=0.0, step=10.0,
                value=float(ligne["tjm_applique"] or tjm_ref or 0),
                key=f"tjm_{ligne['consultant_id']}",
            )
            saisie[ligne["consultant_id"]] = {
                "grade": grade, "nb_jours": nb_jours,
                "tjm_reference": tjm_ref, "tjm_applique": tjm_applique,
            }
            st.caption(f"Total ligne : {finance.total_ligne(nb_jours, tjm_applique):,.2f} €")
            st.divider()

        total = finance.total_mission(saisie.values())
        st.metric("Total mission", f"{total:,.2f} €")

        if st.button("Enregistrer le budget"):
            for consultant_id, champs in saisie.items():
                repository.set_ligne(con, demande_id, consultant_id, **champs)
            st.success("Budget enregistré.")
