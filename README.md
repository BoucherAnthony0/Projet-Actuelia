# Actuelia — Génération de propositions · **Semaine 1**

Premier incrément d'un outil interne qui générera, à terme, des propositions
commerciales PowerPoint à partir d'un appel d'offres.

## Objectif unique de la Semaine 1

**Importer des CV, les structurer automatiquement (LLM), et les afficher.**
Rien d'autre. Pas d'analyse de demande, pas de génération, pas de PowerPoint :
ces briques arrivent aux semaines suivantes.

### Critère de réussite
Je lance l'app, j'importe des CV réels, je les vois listés avec leur séniorité
et leurs années d'expérience correctement extraites.

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

La base `data/actuelia.db` se crée toute seule au 1er lancement.

### Import en masse (optionnel)
Copier d'abord le dossier des CV en local (ne pas pointer le réseau Z:), puis :
```powershell
python ingest_cv.py --cv "C:\chemin\local\CV"
```

## Périmètre — à NE PAS faire cette semaine
- écrans « demande / budget / contenu / export »
- RAG des anciennes propositions (chromadb, embeddings)
- génération PowerPoint
On garde le projet **épuré** ; on empile semaine par semaine.

## Structure
```
app.py            Écran unique : import + liste des CV
config.py         Config (chemins + LLM commutable gratuit/Claude)
schema.sql        Schéma complet de la base (S1 n'utilise que 'consultants')
db/               Connexion + CRUD consultants
core/             parsing (PDF/Word) · llm (commutable) · cv_import
ingest_cv.py      Import en masse depuis un dossier local
tests/test_db.py  Test sans LLM (base + CRUD)
.github/          CI : vérifie chaque push
```

## LLM : gratuit maintenant, Claude plus tard
La couche LLM est **commutable** via `.env` :
- maintenant : `LLM_PROVIDER=openai_compat` (Gemini/Groq gratuits)
- après validation : `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`
Aucun code à modifier pour basculer.
