# DreamGuard — agent notes

## Layout
- `src/dreamguard/` core safety library (no web deps); tests in `tests/`
- `backend/` FastAPI service; run from `backend/`, imports use the `src.` prefix; tests in `backend/tests/`
- `documentation/PRD.md` requirements, `documentation/IMPLEMENTATION_PLAN.md` phase checklist
- `integrations/` Dream-1 loop integration code

## Setup (Windows, Python 3.12)
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,sim]" -r backend/requirements.txt
```

## Verify
```powershell
.\.venv\Scripts\python -m ruff check .                  # core library (backend excluded)
.\.venv\Scripts\python -m pytest -q                     # core + sim + backend tests
.\.venv\Scripts\python -m dreamguard.sim.demo            # offline simulator run with every fault
cd backend; ..\.venv\Scripts\python -m pylint src main.py --fail-under=9.5
cd backend; ..\.venv\Scripts\python main.py             # http://127.0.0.1:8000/docs
```

## Rules
- **No paid Dream API calls** (`client.get_action()`, `python -m dream.check`, `get_models()`) without
  explicit user approval for that specific run. `DreamClient()`, `policy()`, `set_observation()` are local.
- Never read, print or commit `.env`; secrets live only in the repo-root `.env`.
- Implement phase by phase per `IMPLEMENTATION_PLAN.md`; mark items `[x]` when done and ask before
  starting the next phase.
- Backend conventions: config-driven routers from `config_file.json`, one endpoint per file,
  SlowAPI limit on every HTTP route, `log_handler` instead of `print`, service layer in
  `src/resources/`, file header banners with `@author Sebastian Russo`.
- Keep `workers: 1` (in-process simulation/run state).
