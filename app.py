import json
from pathlib import Path
import streamlit as st
import config
from db import init_db, get_connection, repository
from core import analyse, cv_import, finance, parsing, pptx_export, redaction

st.set_page_config(page_title="Actuelia", page_icon="📇", layout="wide")

DEMARCHE_LABELS = redaction.DEMARCHE_LABELS


@st.cache_resource
def _bootstrap():
    return init_db()


_bootstrap()
con = get_connection()

st.title("Actuelia")

tab_accueil, tab_budget, tab_contenu = st.tabs(["Accueil", "Consultants & Budget", "Contenu généré"])


def _demande_selector(demandes: list, key: str) -> int:
    # Le libellé inclut toujours l'id : deux demandes peuvent avoir la même
    # référence/titre/client (ex. titre vide), ce qui collapserait des clés
    # de dict identiques et désynchroniserait l'index du selectbox.
    options = [
        f"{d['reference'] or '(sans réf.)'} — {d['titre'] or ''} ({d['client_nom'] or 'client ?'}) · #{d['id']}"
        for d in demandes
    ]
    ids = [d["id"] for d in demandes]
    default_id = st.session_state.get("demande_active_id", ids[0])
    default_index = ids.index(default_id) if default_id in ids else 0
    choice_index = st.selectbox(
        "Demande active", range(len(options)), index=default_index, key=key,
        format_func=lambda i: options[i],
    )
    demande_id = ids[choice_index]
    st.session_state["demande_active_id"] = demande_id
    return demande_id


# --- Onglet Accueil : import CV + dépôt/analyse d'une demande ---
with tab_accueil:
    fournisseur = "Claude" if config.LLM_PROVIDER == "anthropic" else f"gratuit ({config.LLM_MODEL})"
    c1, c2 = st.columns(2)
    c1.metric("LLM", "configuré" if config.llm_configure() else "non config", fournisseur)
    c2.metric("Consultants en base", repository.count_consultants(con))

    if not config.llm_configure():
        st.info("Renseignez la clé du LLM dans `.env` (voir README) pour activer l'extraction.")

    st.divider()
    st.subheader("Importer des CV (PDF / Word)")
    files = st.file_uploader("Déposer un ou plusieurs CV", type=["pdf", "docx", "doc"],
                             accept_multiple_files=True, key="cv_files")
    if st.button("Importer", disabled=not config.llm_configure(), key="btn_importer_cv"):
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
    if not rows:
        st.caption("Aucun consultant importé pour l'instant.")
    else:
        grades_grille = sorted({
            row["profil_seniorite"]
            for mode in ("regie", "forfait")
            for row in repository.list_grille(con, mode)
            if row["profil_seniorite"] and "Non Actuariat" not in row["profil_seniorite"]
        })
        if not grades_grille:
            st.dataframe([{"id": r["id"], "nom": r["nom"], "prénom": r["prenom"],
                           "titre": r["titre"], "séniorité": r["seniorite"],
                           "années d'XP": r["annees_experience"]} for r in rows],
                         use_container_width=True)
            st.caption(
                "Chargez une grille tarifaire (`python -m db.seed`) pour pouvoir assigner "
                "un grade normalisé à chaque consultant."
            )
        else:
            table_data = [{
                "id": r["id"], "nom": r["nom"], "prénom": r["prenom"], "titre": r["titre"],
                "grade": r["seniorite"] if r["seniorite"] in grades_grille else None,
                "années d'XP": r["annees_experience"],
            } for r in rows]
            edited = st.data_editor(
                table_data,
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "nom": st.column_config.TextColumn(disabled=True),
                    "prénom": st.column_config.TextColumn(disabled=True),
                    "titre": st.column_config.TextColumn(disabled=True),
                    "grade": st.column_config.SelectboxColumn("Grade", options=grades_grille),
                    "années d'XP": st.column_config.NumberColumn(disabled=True),
                },
                hide_index=True, use_container_width=True, key="consultants_grade_editor",
            )
            if st.button("Enregistrer les grades"):
                maj = 0
                for original, edite in zip(table_data, edited):
                    if edite["grade"] and edite["grade"] != original["grade"]:
                        repository.set_seniorite(con, original["id"], edite["grade"])
                        maj += 1
                st.success(f"{maj} grade(s) mis à jour." if maj else "Aucun changement à enregistrer.")

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

    if st.button("Analyser", key="btn_analyser"):
        raw_text, source_name = _request_raw_text()
        if not raw_text:
            st.warning("Déposez un fichier ou collez un texte avant de lancer l'analyse.")
        else:
            st.session_state.request_draft = parsing.build_request_draft(raw_text, source_name)
            st.session_state.request_draft["demande_id"] = st.session_state.request_draft.get("demande_id")

    draft = st.session_state.get("request_draft")
    if draft:
        st.caption("Fiche de demande éditable avant enregistrement")

        if st.button("Lancer l'analyse approfondie (LLM)", disabled=not config.llm_configure(), key="btn_analyse_llm"):
            try:
                enrichie = analyse.analyser_demande(draft.get("texte_brut", ""))
                st.session_state.request_draft = {
                    **draft,
                    "analyse_json": {**(draft.get("analyse_json") or {}), **enrichie},
                }
                draft = st.session_state.request_draft
                st.success("Analyse enrichie par le LLM (contexte, objectifs, enjeux, compétences, planning).")
            except Exception as e:
                st.error(f"Analyse LLM impossible : {e}")

        with st.form("request_validation_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            reference = c1.text_input("Référence", value=draft.get("reference", ""))
            titre = c2.text_input("Titre", value=draft.get("titre", ""))
            client_nom = c1.text_input("Client", value=draft.get("client_nom", ""), key="demande_client_nom")
            mode_facturation = c2.selectbox(
                "Mode de facturation",
                ["", "regie", "forfait"],
                index=["", "regie", "forfait"].index(draft.get("mode_facturation", ""))
                if draft.get("mode_facturation", "") in ["", "regie", "forfait"] else 0,
                key="demande_mode_facturation",
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
            analyse_json_actuel = draft.get("analyse_json", {}) or {}
            contexte_text = st.text_area(
                "Contexte / compréhension du besoin",
                value=analyse_json_actuel.get("contexte", ""),
                height=150,
            )
            objectifs_text = st.text_area(
                "Objectifs (une ligne par objectif)",
                value="\n".join(analyse_json_actuel.get("objectifs", [])),
                height=120,
            )
            enjeux_text = st.text_area(
                "Enjeux (une ligne par enjeu)",
                value="\n".join(analyse_json_actuel.get("enjeux", [])),
                height=120,
            )
            livrables_text = st.text_area(
                "Livrables (une ligne par livrable)",
                value="\n".join(analyse_json_actuel.get("livrables", [])),
                height=150,
            )
            competences_text = st.text_area(
                "Compétences requises (une ligne par compétence)",
                value="\n".join(analyse_json_actuel.get("competences", [])),
                height=120,
            )
            planning_text = st.text_area(
                "Planning / jalons",
                value=analyse_json_actuel.get("planning", ""),
                height=100,
            )
            submitted = st.form_submit_button("Valider et enregistrer")

        if submitted:
            def _lignes(texte: str) -> list[str]:
                return [line.strip() for line in texte.splitlines() if line.strip()]

            analyse_json = {
                **analyse_json_actuel,
                "contexte": contexte_text.strip(),
                "objectifs": _lignes(objectifs_text),
                "enjeux": _lignes(enjeux_text),
                "livrables": _lignes(livrables_text),
                "competences": _lignes(competences_text),
                "planning": planning_text.strip(),
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
            demande_id_form = draft.get("demande_id")
            if demande_id_form:
                repository.update_demande(con, demande_id_form, **payload)
                repository.set_analyse(con, demande_id_form, analyse_json, statut=statut)
            else:
                client_id = repository.get_or_create_client(con, client_nom)
                demande_id_form = repository.create_demande(
                    con,
                    **payload,
                    client_id=client_id,
                )
                repository.set_analyse(con, demande_id_form, analyse_json, statut=statut)
            st.session_state.request_draft = {
                **draft,
                **payload,
                "demande_id": demande_id_form,
                "analyse_json": analyse_json,
            }
            st.session_state["demande_active_id"] = demande_id_form
            stored = repository.get_demande(con, demande_id_form)
            st.success(f"Demande enregistrée (id {demande_id_form})")
            st.json({
                "reference": stored["reference"],
                "titre": stored["titre"],
                "client_nom": stored["client_nom"],
                "statut": stored["statut"],
                "analyse_json": json.loads(stored["analyse_json"]) if stored["analyse_json"] else {},
            })

    st.divider()
    st.subheader("Demandes enregistrées")
    demandes_list = repository.list_demandes(con)
    if demandes_list:
        st.dataframe(
            [{
                "id": d["id"],
                "référence": d["reference"],
                "titre": d["titre"],
                "client": d["client_nom"],
                "statut": d["statut"],
                "date": d["date_depot"],
            } for d in demandes_list],
            use_container_width=True,
        )
    else:
        st.caption("Aucune demande enregistrée pour l'instant.")


demandes = repository.list_demandes(con)

# --- Onglet Consultants & Budget ---
with tab_budget:
    if not demandes:
        st.warning("Aucune demande enregistrée. Déposez et validez une demande dans l'onglet Accueil.")
    else:
        demande_id = _demande_selector(demandes, "select_demande_budget")
        demande = repository.get_demande(con, demande_id)

        st.divider()
        st.subheader("Paramètres de la mission")
        c1, c2 = st.columns(2)
        mode_options = ["", "regie", "forfait"]
        mode_index = mode_options.index(demande["mode_facturation"]) if demande["mode_facturation"] in mode_options else 0
        mode_facturation = c1.selectbox("Mode de facturation", mode_options, index=mode_index, key="budget_mode_facturation")
        client_nom = c2.text_input("Client", value=demande["client_nom"] or "", key="budget_client_nom")

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
            st.caption("Aucun consultant en base. Importez des CV depuis l'onglet Accueil.")
        else:
            with st.form("selection_consultants_form"):
                cases = {}
                for cons in consultants:
                    label = f"{cons['prenom']} {cons['nom']} — {cons['titre'] or cons['seniorite'] or ''}"
                    cases[cons["id"]] = st.checkbox(
                        label, value=cons["id"] in lignes_existantes, key=f"select_{cons['id']}"
                    )
                submitted_selection = st.form_submit_button("Mettre à jour la sélection")

            if submitted_selection:
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


# --- Onglet Contenu généré ---
with tab_contenu:
    if not demandes:
        st.warning("Aucune demande enregistrée. Déposez et validez une demande dans l'onglet Accueil.")
    else:
        demande_id = _demande_selector(demandes, "select_demande_contenu")
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

        lignes_contenu = repository.list_lignes(con, demande_id)
        if not lignes_contenu:
            st.caption("Aucun consultant retenu. Sélectionnez-en depuis l'onglet Consultants & Budget.")
        else:
            for ligne in lignes_contenu:
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

        st.divider()
        st.subheader("Export PowerPoint")

        if not pptx_export.template_disponible():
            st.caption(
                "Template PowerPoint introuvable (`data/template_proposition.pptx`). "
                "Fichier local volontairement hors Git — voir le README."
            )
        else:
            st.caption("L'export reprend le contenu **enregistré** (pensez à « Enregistrer le contenu » avant de générer).")
            st.markdown("**Rédacteur (page de garde)** — laissez vide pour conserver les marqueurs à compléter dans PowerPoint.")
            rc1, rc2 = st.columns(2)
            red_nom = rc1.text_input("Nom du rédacteur", key="red_nom")
            red_fonction = rc2.text_input("Fonction", key="red_fonction")
            red_email = rc1.text_input("Email", key="red_email")
            red_tel = rc2.text_input("Téléphone", key="red_tel")
            if st.button("Générer le PowerPoint"):
                lignes_budget = repository.list_lignes(con, demande_id)
                nom_fichier = f"{(demande['reference'] or f'demande-{demande_id}').replace(' ', '_')}.pptx"
                chemin_sortie = config.PROPOSITIONS_DIR / nom_fichier
                contenu_persiste = json.loads(demande["contenu_genere_json"]) if demande["contenu_genere_json"] else None
                redacteur = {"nom": red_nom, "fonction": red_fonction, "email": red_email, "telephone": red_tel}
                try:
                    total = pptx_export.generer_pptx(demande=demande, lignes=lignes_budget,
                                                     chemin_sortie=chemin_sortie, contenu=contenu_persiste,
                                                     redacteur=redacteur)
                    repository.create_proposition(
                        con, demande_id=demande_id, client_id=demande["client_id"],
                        titre=demande["titre"], chemin_pptx=str(chemin_sortie),
                    )
                    st.session_state["pptx_genere"] = str(chemin_sortie)
                    st.success(f"PowerPoint généré (budget total : {total:,.0f} €).".replace(",", " "))
                except Exception as e:
                    st.error(f"Génération impossible : {e}")

        chemin_genere = st.session_state.get("pptx_genere")
        if chemin_genere and Path(chemin_genere).exists():
            with open(chemin_genere, "rb") as f:
                st.download_button(
                    "Télécharger le PowerPoint",
                    data=f.read(),
                    file_name=Path(chemin_genere).name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
