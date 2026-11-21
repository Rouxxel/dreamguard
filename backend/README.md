# DreamGuard Backend

FastAPI service for DreamGuard. It exposes the safety supervisor, simulation runs and safety
event history to the React dashboard, with rate limiting, structured logging and JSON-based
configuration.

## Features

- **FastAPI**: REST endpoints plus interactive docs at `/docs`
- **Rate limiting**: per-endpoint limits with SlowAPI, configured in `config_file.json`
- **Logging**: timestamped log files in `backend/logs/` plus console output
- **Configuration**: JSON-based settings via `config_loader`, static reference data via `data_loader`
- **CORS**: dashboard origins configured in `config_file.json`
- **Security**: non-root Docker user, secrets only from `.env`, RSA and hardened file I/O utilities
- **Docker**: multi-stage `DOCKERFILE` and `docker-compose.yml`

## Project Structure

```
backend/
├── src/
│   ├── api_endpoints/              # API route definitions
│   │   ├── routers/                # One folder per endpoint group, one endpoint per file
│   │   └── root_endpoint.py        # Root / health-check endpoint
│   ├── core_specs/                 # Core configuration and static data
│   │   ├── configuration/
│   │   │   ├── config_file.json    # Paths, logging, network and endpoint settings
│   │   │   └── config_loader.py    # Loads config_file.json -> config_loader
│   │   └── data/
│   │       ├── general_data.json   # Static reference data
│   │       └── data_loader.py      # Loads general_data.json -> data_loader
│   ├── models/                     # Pydantic models (Base / Create / Update / Entity / Response)
│   ├── resources/                  # Service layer used by routers
│   └── utils/
│       ├── custom_logger.py        # Logging configuration (log_handler)
│       ├── limiter.py              # Shared SlowAPI limiter instance
│       ├── request_limiter.py      # 429 handler for rate-limit exceeded
│       ├── en_de_crypt.py          # RSA encrypt/decrypt (requires .env keys)
│       ├── keys_generator.py       # One-off script to generate an RSA key pair
│       ├── keys_generator_dtrmnstc.py  # Deterministic Ed25519 key pair from a passphrase
│       └── secure_file_io.py       # Hardened atomic file read/write helpers
├── tests/                          # Backend tests (pytest + FastAPI TestClient)
├── logs/                           # Log files (created automatically, git-ignored)
├── main.py                         # Application entry point
├── requirements.txt                # Backend Python dependencies
├── start.sh / start.bat            # Dev setup and launch scripts
├── DOCKERFILE                      # Docker build configuration
├── docker-compose.yml              # Docker compose configuration
├── .dockerignore
├── .pylintrc
└── README.md
```

## Quick Start

### Option 1: Run with Python (development)

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env    # only if .env does not exist yet
```

Then run the backend from the `backend` folder:

```powershell
cd backend
python main.py
# or: uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`start.bat` / `start.sh` perform the same setup interactively.

- API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Option 2: Run with Docker

```powershell
cd backend
docker compose up --build
```

The container reads secrets from the repository-level `.env` at runtime (`env_file: ../.env`);
`.env` files are excluded from the image by `.dockerignore`.

## Configuration

### Environment Variables (`../.env`)

The backend loads the repository-level `.env` (path set by `defaults.env_file_path`).
See `../.env.example` for every variable:

| Variable | Purpose |
|---|---|
| `DREAM_API_KEY` | Dream Labs API key |
| `DREAMGUARD_ALLOW_PAID` | Must be `1` before any paid Dream-1 inference call is allowed |
| `API_TITLE`, `API_VERSION`, `API_DESCRIPTION` | OpenAPI metadata |
| `SERVER_PORT` | Host port published by docker-compose |
| `E_PRIVATE_KEY`, `E_PRIVATE_PASSWORD`, `E_PUBLIC_KEY` | RSA keys used by `en_de_crypt.py` |

### JSON Configuration (`config_file.json` + `config_loader`)

`config_loader.py` reads `config_file.json` at import time and exposes it as `config_loader`
(a dict). Relative paths inside the file are resolved against the `backend/` folder with
`resolve_backend_path`, so the backend works from any working directory. Every router pulls its
prefix, tag, route and rate-limit values from here rather than hard-coding them.

| Section | Purpose |
|---|---|
| `defaults` | Shared paths (general data, repository `.env`) |
| `logging` | Log level, directory, file name prefix |
| `network` | Uvicorn host, port, workers, reload, proxy headers, CORS origins |
| `endpoints` | Per-endpoint prefix, tag, route and rate-limit settings |

**Endpoint config shape** (one entry per route):

```json
"root_directory_endpoint": {
    "request_limit": 60,
    "unit_of_time_for_limit": "m",
    "endpoint_prefix": "",
    "endpoint_tag": "health",
    "endpoint_route": "/"
}
```

**Usage in a router:**

```python
from src.core_specs.configuration.config_loader import config_loader
from src.utils.limiter import limiter as SlowLimiter

cfg = config_loader["endpoints"]["root_directory_endpoint"]

router = APIRouter(prefix=cfg["endpoint_prefix"], tags=[cfg["endpoint_tag"]])

@router.get(cfg["endpoint_route"])
@SlowLimiter.limit(f"{cfg['request_limit']}/{cfg['unit_of_time_for_limit']}")
async def root_endpoint(request: Request):
    ...
```

`workers` must stay at `1`: simulation runs and live event streams are held in process memory.
WebSocket routes are not covered by SlowAPI rate limiting.

### Static Data (`general_data.json` + `data_loader`)

`data_loader.py` works the same way as `config_loader` but loads the file referenced by
`defaults.general_data_path`. Use it for reference data that is not environment-specific.

```python
from src.core_specs.data.data_loader import data_loader

project = data_loader["metadata"]["project"]
```

## Adding New Endpoints

Each endpoint group follows the same conventions:

1. **Config-driven router**: prefix, tag, route and rate limits from `config_loader`
2. **One endpoint per file** inside `src/api_endpoints/routers/<group>/`
3. **Pydantic models** in `src/models/`
4. **Service layer**: business logic in `src/resources/`, not in route handlers
5. **Logging**: `log_handler` instead of `print`
6. **Rate limiting**: `@SlowLimiter.limit(...)` on every HTTP route

**Steps:**

1. Add an entry under `endpoints` in `config_file.json`.
2. Create the router file under `src/api_endpoints/routers/<group>/`.
3. Create matching Pydantic models in `src/models/` using the split below.
4. Register the router in `main.py`:
   ```python
   from src.api_endpoints.routers.<group>.<file> import router as <name>_router
   app.include_router(<name>_router)
   ```

**Current endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |

## Models (`src/models/`)

Recommended Pydantic split for any entity:

| Class | Role |
|---|---|
| `*Base` | Domain fields shared by every variant |
| `*Create` | POST body (no server-managed fields like `id`) |
| `*Update` | PATCH body (all fields optional) |
| `*<Entity>` | Full persisted record including `id` |
| `*Response` | API response shape (decoupled from storage) |

## Utilities (`src/utils/`)

| Module | When to use |
|---|---|
| `custom_logger.py` | `log_handler`: use everywhere instead of `print` |
| `limiter.py` | Shared `limiter` instance; decorate routes with `@limiter.limit(...)` |
| `request_limiter.py` | Registered in `main.py` as the global 429 handler |
| `en_de_crypt.py` | `encrypt_in` / `decrypt_out` for RSA-encrypted fields; raises at import if the RSA keys are not set, so import it only where it is needed |
| `keys_generator.py` | Run once to generate an RSA key pair for `.env` |
| `keys_generator_dtrmnstc.py` | Reproducible Ed25519 key pair from a passphrase (not compatible with `en_de_crypt.py`) |
| `secure_file_io.py` | Safe atomic file reads/writes with path confinement |

Generated `*.pem` files are git-ignored.

## Security Features

- **Rate limiting**: configurable per-endpoint limits via `config_file.json`
- **Input validation**: Pydantic models
- **Encryption**: RSA utilities in `en_de_crypt.py` (keys from environment)
- **Non-root Docker**: container runs as a non-root user
- **Secrets**: only from `.env`, never committed and never copied into images
- **Local binding**: binds to `127.0.0.1` by default

## Logging

- **File logging**: timestamped log files in `backend/logs/`
- **Console logging**: structured output for containers
- **Configurable levels**: `logging.logging_level` in `config_file.json`
- **Request logging**: rate-limit violations logged at warning level

## Development

### Running Tests

From the repository root:

```powershell
python -m pytest backend/tests
```

### Linting

```powershell
cd backend
pylint src main.py
```

### Adding Dependencies

Add the pinned package to `requirements.txt` and reinstall:

```powershell
python -m pip install -r backend/requirements.txt
```

## Requirements

- Python 3.12
- Docker (optional)

