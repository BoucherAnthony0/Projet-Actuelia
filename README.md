# FastAPI API

## Structure

- `app/main.py`: application FastAPI
- `app/core/config.py`: configuration centralisée
- `app/api/v1`: routeurs et endpoints versionnés
- `tests/`: tests de base

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```
