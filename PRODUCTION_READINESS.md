# Production Readiness

Tracks what's built to real production standards vs. what a genuine
deployment would still need. Updated per phase.

## Application layer (built to production standards)

- [x] Environment-based configuration (`pydantic-settings`, `.env`, no
      hardcoded secrets) — `backend/app/config.py`
- [x] Swappable LLM provider abstraction (`LLMProvider` ABC; Ollama today,
      OpenAI/Gemini are config-only swaps) — `backend/app/rag/llm.py`
- [x] Stateless API (JWT bearer auth, no server-side session state)
- [x] Password hashing via bcrypt (not reversible, not plaintext)
- [x] Authorization enforced at the data layer, never trusted from a
      downstream system (Qdrant) — every retrieval re-verified against
      PostgreSQL
- [x] Versioned DB schema via Alembic migrations (not ad-hoc DDL)
- [x] Automated security regression tests (tenant isolation, role
      permissions, retriever-bypass) run in CI-able form via `pytest`

## Explicitly out of scope for this portfolio project

- [ ] Managed cloud database (RDS/Cloud SQL) — using self-hosted Postgres
      via Docker Compose
- [ ] Secrets vault (Vault/AWS Secrets Manager) — using `.env` files
- [ ] Autoscaling / container orchestration (Kubernetes) — using Docker
      Compose only
- [ ] Real load testing (k6/Locust) — not performed
- [ ] Rate limiting — planned for Phase 5
- [ ] TLS termination / production ingress — not configured
- [ ] Multi-region / DR / backup strategy — not configured
- [ ] Observability stack (OpenTelemetry, Prometheus, Grafana) — planned
      for Phase 5

## Why this split is deliberate

The application layer (auth, tenant isolation, policy decisions, audit
trail, security tests) is where AI security engineering actually lives,
and is built as if for production. Infra concerns (managed DB, secrets
vault, autoscaling) are standard DevOps/platform work, not the focus of
this project, and are structured so adding them later is a deployment
change, not an application rewrite — e.g. `DATABASE_URL` already points
at any Postgres-compatible connection string, so swapping Docker Compose
Postgres for RDS requires no code change.

## Phase 1 specific notes

- LLM provider defaults to **Ollama** (local, free) because no API
  credits are currently available. `LLM_PROVIDER=openai` in `.env` swaps
  to OpenAI once credits exist — no code change required.
- Embeddings use a local `sentence-transformers` model
  (`all-MiniLM-L6-v2`) — free, deterministic, no external API dependency.
