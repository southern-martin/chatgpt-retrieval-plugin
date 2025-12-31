# AGENTS

This file provides quick, practical guidance for coding agents working in this repo.

## Repo map

- `server/` — FastAPI app entrypoint (`server/main.py`).
- `datastore/` — vector database providers and query/upsert logic.
- `models/` — request/response and document metadata models.
- `services/` — chunking, metadata extraction, file processing utilities.
- `scripts/` — import and processing scripts.
- `.well-known/` — OpenAPI and plugin manifest assets.
- `tests/` — integration tests (provider-specific).

## Setup (local)

- Python 3.10 + Poetry.
- `poetry install`
- Configure env vars (see `.env.example` and `README.md`).
- Run: `poetry run uvicorn server.main:app --host 0.0.0.0 --port 8000`

## Conventions

- Keep secrets out of git; update `.env.example` when adding new env vars.
- Prefer small, focused changes; update docs when behavior changes.
- Respect existing formatting; avoid reformatting entire files without need.

## Notes

- CORS is configurable via `CORS_ALLOW_ORIGINS` (comma-separated).
