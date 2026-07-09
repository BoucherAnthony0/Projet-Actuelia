# Actuelia — Génération de propositions · **Semaine 4 (en cours)**

Outil interne qui génère le contenu d'une proposition commerciale en réponse à
un appel d'offres. Le calcul financier est **100% déterministe** (jamais
confié au LLM) ; la couche LLM est **commutable** (gratuit maintenant, Claude
en fin de projet).

## Ce qui est livré (S1 → S3)

- **S1 — Import CV** : import de CV (PDF/Word), structuration automatique par
  LLM, liste des consultants.
- **S2 — Dépôt & analyse de la demande** : import d'un appel d'offres
  (PDF/Word/texte/email), extraction rapide (référence, titre, client,
  livrables), puis analyse LLM enrichie (contexte, objectifs, enjeux,
  compétences, planning), éditable et persistée.
- **S3 — Proposition** :
  - sélection manuelle des consultants retenus pour une demande + mode de
    facturation (régie/forfait) et client ;
  - tableau financier par lignes (grade, jours, tarif), total 100%
    déterministe, avec une grille tarifaire de référence ;
  - rédaction LLM du contexte et de la démarche d'intervention (cadrage /
    analyse / réalisation / accompagnement / restitution), éditable ;
  - synthèse CV par consultant retenu, ciblée sur le besoin, sans invention
    (strictement bornée au CV réel importé).

- **S4 — Export PowerPoint** *(en cours)* : génération d'une proposition
  `.pptx` fidèle au template de marque Actuelia (page de garde, présentation
  du cabinet, budget), à partir des données déjà saisies. Phase 1 livrée :
  couverture, sommaire, présentation du cabinet, budget par ligne, slide de
  fin. À venir : slides contexte/démarche, fiches CV par consultant.

### Hors périmètre pour l'instant
- RAG des anciennes propositions / chromadb / embeddings (Semaine 5)

### Piste future — déploiement réseau interne
Idée à instruire plus tard : héberger l'app sur le PC de la société qui tourne
H24/7j, avec les consultants qui y accèdent via une adresse mise en favori
(plutôt qu'un lancement manuel par poste).
- Techniquement, Streamlit le permet nativement : `streamlit run app.py
  --server.address 0.0.0.0 --server.port 8501`, accessible depuis le réseau
  local à `http://<ip-du-pc>:8501`.
- Prérequis côté infra (hors dépôt) : IP fixe réservée pour ce PC sur le
  routeur, et le processus enregistré comme service qui redémarre seul
  (NSSM ou tâche planifiée au démarrage sous Windows).
- Point à trancher avant de le faire : aucune authentification aujourd'hui —
  toute personne sur le réseau de l'entreprise ayant l'adresse peut voir et
  modifier CV, budgets et propositions.

## Installation (Windows / PowerShell)

Lancer les commandes **une par une** (PowerShell n'accepte pas `&&`) :

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # débloque l'activation
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Puis ouvrir `.env` et coller une clé LLM **gratuite** :
- Google AI Studio (recommandé) : https://aistudio.google.com/apikey → coller dans `LLM_API_KEY`
- ou Groq : https://console.groq.com (décommenter les 2 lignes Groq dans `.env`)

## Lancement

```powershell
streamlit run app.py
```

La base `data/actuelia.db` se crée toute seule au 1er lancement (les
migrations de schéma s'appliquent automatiquement aux bases déjà existantes).

### Écrans
Une seule page (`app.py`), organisée en onglets :
- **Accueil** : import de CV, dépôt et analyse d'une demande.
- **Consultants & Budget** : demande active, mode de facturation / client,
  sélection des consultants, tableau financier.
- **Contenu généré** : contexte rédigé, démarche d'intervention, synthèse CV
  par consultant retenu — tout est éditable.

### Grille tarifaire (optionnel)
```powershell
python -m db.seed
```
Insère les TJM de référence par grade, utilisés pour pré-remplir le tarif de
référence dans le tableau financier.

- Si `data/grille_tarifaire.json` existe, le seed charge **cette grille**
  (la vraie grille Actuelia, forfait/régie × actuariat/non actuariat). Ce
  fichier est **volontairement exclu de Git** (`.gitignore`) car les tarifs
  sont confidentiels — à copier manuellement sur chaque poste, jamais à
  committer. Format attendu :
  ```json
  {
    "forfait": {"Associé": {"actuariat": 2360, "non_actuariat": 1888}, "...": {}},
    "regie":   {"Associé": {"actuariat": 1910, "non_actuariat": 1528}, "...": {}}
  }
  ```
- Sinon, il retombe sur une grille de démonstration (valeurs fictives, mode
  régie uniquement) — suffisant pour un dépôt fraîchement cloné ou la CI.

### Export PowerPoint (optionnel)
Pose le template de marque Actuelia dans `data/template_proposition.pptx`.
Comme la grille tarifaire, ce fichier est **volontairement exclu de Git**
(contenu de marque + exemples de missions clientes réelles) — à copier
manuellement sur chaque poste, jamais à committer. Sans lui, le bouton
« Générer le PowerPoint » (onglet Contenu généré) reste indisponible.

### Import en masse de CV (optionnel)
Copier d'abord le dossier des CV en local (ne pas pointer le réseau Z:), puis :
```powershell
python ingest_cv.py --cv "C:\chemin\local\CV"
```

## Tests

```powershell
pytest -q
python tests/test_db.py
```

## Structure
```
app.py                     Page unique à onglets : Accueil, Consultants & Budget, Contenu généré
config.py                  Config (chemins + LLM commutable gratuit/Claude)
schema.sql                 Schéma complet de la base
db/                        Connexion + migrations + CRUD + seed grille tarifaire
core/                      parsing · analyse · redaction · finance · pptx_export · llm · cv_import
ingest_cv.py               Import en masse depuis un dossier local
tests/                     Suite pytest (LLM mocké, pas de dépendance réseau en CI)
.github/                   CI : compilation + pytest à chaque push
```

## LLM : gratuit maintenant, Claude plus tard
La couche LLM est **commutable** via `.env` :
- maintenant : `LLM_PROVIDER=openai_compat` (Gemini/Groq gratuits)
- après validation : `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`
Aucun code à modifier pour basculer.
