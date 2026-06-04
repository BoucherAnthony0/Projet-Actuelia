# Travailler sur le projet (guide Git)

Contexte : développement en autonomie pendant l'absence du référent.
Objectif : avancer proprement, sans casser ce qui marche.

## Règles d'or
1. **Ne jamais committer** : `.env`, le dossier `data/`, `.venv/`
   (déjà couverts par `.gitignore` — ne pas le modifier).
2. **Une branche par tâche**, jamais de push direct sur `main`.
3. **Lancer le test avant de pousser** : `python tests/test_db.py` doit afficher `test_db OK`.
4. Rester dans le périmètre S1 (voir README) : on n'ajoute pas les briques futures.

## Cycle de travail
```bash
git checkout main
git pull
git checkout -b feat/ma-tache        # ex : feat/ameliore-extraction-cv
# ... modifications ...
python tests/test_db.py              # vérifier que ça passe
git add -A
git commit -m "feat: description courte et claire"
git push -u origin feat/ma-tache
```
Puis ouvrir une **Pull Request** (ou Merge Request) vers `main` et la laisser
en revue. La CI GitHub vérifie automatiquement la compilation et le test.

## Convention de messages de commit
- `feat:` nouvelle fonctionnalité
- `fix:` correction de bug
- `docs:` documentation
- `refactor:` réorganisation sans changement de comportement

## Si quelque chose bloque
Noter le problème dans une *issue* GitHub (message d'erreur complet + ce que
vous essayiez de faire) plutôt que de forcer une solution risquée.
