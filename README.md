# Sentinel — Secure Multi-Tenant Agentic RAG

![tests](https://github.com/yashb-16/Sentinel-AI-security/actions/workflows/tests.yml/badge.svg)

Most RAG demos ignore security. Sentinel is an agentic RAG backend where every
layer assumes the LLM can be tricked, and enforces safety deterministically outside the model.

## Security layers

| Phase | Layer | What it does |
|-------|-------|--------------|
| 1 | Auth + tenant isolation | JWT auth, roles (employee/hr/admin). Qdrant is only a performance filter — every retrieved document is re-verified against PostgreSQL. |
| 2 | Prompt-injection defense | Retrieved docs wrapped as untrusted content; tested against 6 attack techniques, before/after. |
| 3 | Tool Gateway | Policy engine (ALLOW / DENY / REQUIRE_APPROVAL) + risk engine (LOW–CRITICAL). Identity is server-injected, never LLM-controlled. HIGH/CRITICAL actions need admin approval. |
| 4 | DLP / output validation | Blocks credentials, redacts email/phone, role-aware salary redaction. Logs categories only, never raw values. |

## Stack
Python 3.11, FastAPI, LangGraph, PostgreSQL, Qdrant, Alembic, Ollama (swappable LLM provider), Docker Compose, uv, pytest.

## Run
```bash
cp .env.example .env
docker compose up -d
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir backend
```
Endpoints: `POST /auth/login`, `POST /ask`, `GET /approvals`, `POST /approvals/{id}/decide`.

## Test
```bash
uv run pytest   # 111 tests, no network/GPU needed (LLM and vector store are faked)
```

## Measured results
On independent data (Faker, real prose, public injection dataset) the DLP layer went from **39% to 94% recall** after
a measure-and-fix cycle, at a cost of 0.1% false positives; the injection defense could not be shown to help on
small real models (they already resisted). Full methodology and limitations: [`docs/benchmarks.md`](docs/benchmarks.md).

## Docs
Design notes and real findings per phase are in [`docs/`](docs/); status in [`PROGRESS.md`](PROGRESS.md);
known gaps in [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md).

## Author
Built by [Yash Bansal](https://github.com/yashb-16).
