# HelixDB — Architecture and Development Guide

## Layout

```
backend/
  main.py            FastAPI app factory: routers, CORS, static frontend
  api/               HTTP routers (auth, events, reports, research, users, …)
  config/settings.py Runtime configuration via pydantic-settings
  database/          SQLite schema and helpers (relational.py)
  schemas/           Pydantic request/response models
  services/          Domain logic (scoring, OCR, import, analytics, neurobot)
tests/               Test suite (pytest)
main.py              Root entry point: `python main.py`
```

The `backend` package is imported through its real dotted path
(`backend.services.scoring`), never as a top-level `services` module, so
relative imports inside the service layer resolve correctly.

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python main.py                  # 127.0.0.1:8123
python main.py --port 9000
python main.py --reload
```

Equivalent without installing the project:

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --port 8123
```

`backend/dev.sh` wraps the same commands (`serve`, `start`, `stop`, `test`).

## Tests

```bash
python -m pytest tests -q
```

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["."]`, so
pytest needs no extra flags from the repository root.

The current suite covers the cognitive-robotics service
(`backend/services/neurobot.py`): organoid/MEA spike-tensor statistics, window
slicing, closed-loop maze control, the adversarial stress suite, and the
integrated readiness gate.

## Database

`backend/database/relational.py` owns the SQLite schema and exposes `init_db`,
`cursor`, `now_iso`, `row_to_dict` and `rows_to_dicts`. Import and export
routers depend on those helpers, so schema changes belong in that module rather
than in a router.

Runtime database files are written under `backend/data/` and are git-ignored.

## Configuration

Settings are read by `backend/config/settings.py` through
`pydantic-settings`, so any field can be overridden with an environment
variable. Do not commit `.env`.
