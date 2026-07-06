-- =============================================================
--  Plateforme de réponse automatisée aux appels d'offres
--  Schéma SQLite — stockage local persistant
--  (les vecteurs des anciennes propales vivent dans Chroma,
--   cette base ne stocke que le structuré + les métadonnées)
-- =============================================================
--  Initialisation :  sqlite3 actuelia.db < schema.sql
--  Important : activer les clés étrangères à CHAQUE connexion :
--      PRAGMA foreign_keys = ON;
-- =============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;   -- meilleures perfs en lecture/écriture concurrente

-- -------------------------------------------------------------
--  Méta : version de schéma (utile pour les futures migrations)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_meta (
    cle     TEXT PRIMARY KEY,
    valeur  TEXT
);
INSERT OR IGNORE INTO app_meta (cle, valeur) VALUES ('schema_version', '1');

-- -------------------------------------------------------------
--  CLIENTS  —  DIMENSION ACCUMULÉE AUTOMATIQUEMENT (optionnelle)
--  Ce N'EST PAS un référentiel maître saisi à la main.
--  Le nom et le logo du client sont extraits de chaque appel
--  d'offres (voir table 'demandes'). Cette table est remplie/
--  enrichie tout seul par l'outil au fil des AO traités (upsert) :
--    - 1ère fois qu'on voit un client  -> création
--    - fois suivantes                  -> on réutilise / enrichit
--  Intérêt : réutiliser un logo déjà nettoyé, accumuler des notes,
--  et relier les propales d'un même client (missions similaires).
--  Si on ignore cette table, l'app fonctionne avec les champs
--  portés directement par la demande.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY,
    nom             TEXT NOT NULL UNIQUE,
    secteur         TEXT,
    logo_path       TEXT,             -- logo canonique réutilisable (issu d'un AO précédent)
    notes           TEXT,             -- informations spécifiques accumulées au fil des AO
    nb_demandes     INTEGER NOT NULL DEFAULT 0,
    premiere_vue    TEXT NOT NULL DEFAULT (datetime('now')),
    derniere_vue    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- -------------------------------------------------------------
--  CONSULTANTS  (importés une fois, choisis manuellement)
--  cv_complet_json = profil structuré extrait par le LLM
--  (dans lequel le synthétiseur pioche pour la slide CV)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultants (
    id                  INTEGER PRIMARY KEY,
    nom                 TEXT NOT NULL,
    prenom              TEXT NOT NULL,
    titre               TEXT,             -- ex. "Actuaire Senior"
    seniorite           TEXT,             -- ex. "Niveau 2 (4 à 7 ans)"
    role_principal      TEXT,
    annees_experience   INTEGER,
    email               TEXT,
    photo_path          TEXT,             -- chemin local de la photo
    formation           TEXT,
    cv_complet_json     TEXT,             -- JSON : expériences, compétences, etc.
    chemin_cv_source    TEXT,             -- fichier d'origine importé
    actif               INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0,1)),
    date_import         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Expériences détaillées (alimentées par l'extraction LLM).
-- Facultatif si tout est déjà dans cv_complet_json, mais utile
-- pour filtrer/synthétiser les expériences pertinentes par mission.
CREATE TABLE IF NOT EXISTS consultant_experiences (
    id              INTEGER PRIMARY KEY,
    consultant_id   INTEGER NOT NULL,
    client          TEXT,                 -- nom du client de la mission passée
    secteur         TEXT,
    role            TEXT,
    description     TEXT,
    technologies    TEXT,
    date_debut      TEXT,                 -- ISO 8601 "AAAA-MM-JJ"
    date_fin        TEXT,
    FOREIGN KEY (consultant_id) REFERENCES consultants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS consultant_competences (
    id              INTEGER PRIMARY KEY,
    consultant_id   INTEGER NOT NULL,
    libelle         TEXT NOT NULL,
    categorie       TEXT,                 -- ex. "fonctionnelle" / "technique"
    niveau          TEXT,                 -- ex. "expert" / "maîtrise"
    FOREIGN KEY (consultant_id) REFERENCES consultants(id) ON DELETE CASCADE
);

-- -------------------------------------------------------------
--  GRILLES TARIFAIRES  (donnée interne — votre tarification)
--  client_id NULL = grille générique ; sinon grille propre au client.
--  Permet : régie/forfait, tarif par grade, tarif par client.
--  RÔLE : sert de RÉFÉRENCE affichée dans l'interface pour guider.
--  Le tarif réellement facturé est saisi / confirmé À LA MAIN sur
--  chaque ligne (cf. demande_consultants.tjm_applique) : ça évite
--  les erreurs et autorise les remises négociées par client.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS grilles_tarifaires (
    id                  INTEGER PRIMARY KEY,
    mode                TEXT NOT NULL CHECK (mode IN ('regie','forfait')),
    client_id           INTEGER,          -- NULL = s'applique à tous
    profil_seniorite    TEXT,             -- ex. "Senior", "Niveau 2"
    tjm                 REAL NOT NULL,    -- tarif journalier en euros HT
    devise              TEXT NOT NULL DEFAULT 'EUR',
    date_validite       TEXT,
    actif               INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0,1)),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

-- -------------------------------------------------------------
--  DEMANDES  (l'appel d'offres déposé + son analyse)
--  analyse_json = sortie structurée du LLM
--  (contexte, objectifs, enjeux, livrables, planning, compétences)
--  La facturation se calcule depuis les LIGNES (demande_consultants).
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demandes (
    id                  INTEGER PRIMARY KEY,
    titre               TEXT,
    reference           TEXT,             -- ex. "RFX008792"
    client_nom          TEXT,             -- nom du client EXTRAIT de l'AO
    client_logo_path    TEXT,             -- logo EXTRAIT de cet AO (source de vérité page de garde)
    client_id           INTEGER,          -- lien OPTIONNEL vers la dimension clients (résolu par nom)
    statut              TEXT NOT NULL DEFAULT 'brouillon'
                        CHECK (statut IN ('brouillon','analyse','en_cours',
                                          'generee','envoyee','gagnee','perdue')),
    texte_brut          TEXT,             -- contenu parsé de la demande
    analyse_json        TEXT,             -- analyse structurée (LLM)
    contenu_genere_json TEXT,             -- rédaction (LLM) : contexte + démarche, éditable
    mode_facturation    TEXT CHECK (mode_facturation IN ('regie','forfait')),
    nb_jours            REAL,             -- indicatif (issu de l'AO) ; total réel = somme des lignes
    date_depot          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

-- Consultants retenus pour une demande (sélection MANUELLE).
-- = LIGNES de la proposition financière : un grade, un nombre de
--   jours et un tarif PAR collaborateur. Plusieurs grades / volumes
--   différents sur une même mission sont donc gérés nativement.
-- tjm_reference = tarif suggéré par la grille (indicatif, lecture seule)
-- tjm_applique  = tarif RÉELLEMENT facturé, saisi/confirmé à la main
--                 (permet remises client, ou TJM unique négocié)
-- Total d'une ligne = nb_jours * tjm_applique ; total mission = somme.
CREATE TABLE IF NOT EXISTS demande_consultants (
    demande_id      INTEGER NOT NULL,
    consultant_id   INTEGER NOT NULL,
    role_sur_mission TEXT,
    grade           TEXT,                 -- grade retenu pour la facturation (souvent = séniorité)
    nb_jours        REAL NOT NULL DEFAULT 0,
    tjm_reference   REAL,                 -- pré-rempli depuis la grille (indicatif)
    tjm_applique    REAL,                 -- tarif facturé, SAISI À LA MAIN
    synthese_cv     TEXT,                 -- synthèse CV (LLM) ciblée mission, éditable, zéro invention
    ordre           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (demande_id, consultant_id),
    FOREIGN KEY (demande_id)    REFERENCES demandes(id)    ON DELETE CASCADE,
    FOREIGN KEY (consultant_id) REFERENCES consultants(id) ON DELETE CASCADE
);

-- -------------------------------------------------------------
--  PROPOSITIONS  (métadonnées des propales produites / passées)
--  Les vecteurs pour le RAG sont dans Chroma ; ici on garde
--  la traçabilité + le lien vers le .pptx généré.
--  chroma_doc_id = identifiant du document dans l'index local.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS propositions (
    id                  INTEGER PRIMARY KEY,
    demande_id          INTEGER,          -- NULL pour les propales historiques importées
    client_id           INTEGER,
    titre               TEXT,
    secteur             TEXT,
    chemin_pptx         TEXT,
    chroma_doc_id       TEXT,             -- clé de l'entrée dans l'index vectoriel
    gagnee              INTEGER CHECK (gagnee IN (0,1)),   -- NULL = inconnu
    origine             TEXT NOT NULL DEFAULT 'generee'
                        CHECK (origine IN ('generee','historique')),
    date_generation     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (demande_id) REFERENCES demandes(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id)  REFERENCES clients(id)  ON DELETE SET NULL
);

-- -------------------------------------------------------------
--  INDEX  (accélèrent les jointures et recherches courantes)
-- -------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_exp_consultant    ON consultant_experiences(consultant_id);
CREATE INDEX IF NOT EXISTS idx_comp_consultant   ON consultant_competences(consultant_id);
CREATE INDEX IF NOT EXISTS idx_grille_client     ON grilles_tarifaires(client_id);
CREATE INDEX IF NOT EXISTS idx_grille_mode       ON grilles_tarifaires(mode);
CREATE INDEX IF NOT EXISTS idx_demande_client    ON demandes(client_id);
CREATE INDEX IF NOT EXISTS idx_demande_statut    ON demandes(statut);
CREATE INDEX IF NOT EXISTS idx_dc_consultant     ON demande_consultants(consultant_id);
CREATE INDEX IF NOT EXISTS idx_prop_client       ON propositions(client_id);
CREATE INDEX IF NOT EXISTS idx_prop_origine      ON propositions(origine);
