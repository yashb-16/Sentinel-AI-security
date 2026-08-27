# Sentinel — Progress Log

## Current Phase
Phase 1 — Vertical Slice (Auth + Tenant-Isolated RAG)

## Status
Implementation complete, all tests GREEN, manual end-to-end verification
passed against real Postgres + Qdrant + Ollama. Awaiting Step 7: your
manual review and sign-off before anything is committed.

## Completed
- [x] Master project context captured, Phase 1 objective and detailed
      plan produced and approved (2026-08-27)
- [x] `PROGRESS.md` baseline created (2026-08-27)
- [x] Step 3: wrote 16 tests across `test_auth.py`, `test_tenant_isolation.py`,
      `test_role_permissions.py`, `test_retriever_bypass.py`,
      `test_ask_endpoint.py` — confirmed RED (ModuleNotFoundError, nothing
      implemented yet) (2026-08-27)
- [x] Step 4: implemented Phase 1 — config, DB models (Tenant/User/Document),
      JWT auth, tenant/role-filtered retriever with mandatory Postgres
      re-verification, Qdrant vector store, Ollama/OpenAI-swappable LLM
      provider, `/auth/login` and `/ask` endpoints, Alembic migrations,
      seed script (2026-08-27)
- [x] Step 5: all 16 tests GREEN (2026-08-27)
- [x] Step 6: end-to-end manual review — verified live against real
      Postgres + Qdrant + a locally-pulled Ollama model
      (`llama3.2:1b`): Acme employee correctly denied the HR-confidential
      salary doc, Acme HR correctly granted it, Acme employee got zero
      Globex documents even when asking about Globex content directly
      (2026-08-27)
- [x] `PRODUCTION_READINESS.md` created (2026-08-27)
- [x] `docs/phase-1-notes.md` written — real bugs hit during
      implementation (SQLite thread-pooling gotcha, str-enum `__str__`
      surprise, reserved-TLD email validation, qdrant-client API
      removal) (2026-08-27)

## In Progress
- [ ] Step 7: your manual review — nothing committed until you sign off

## Next Steps
- [ ] Step 7: user manual review and sign-off
- [ ] Step 8: commit to `phase-1-auth-rag` branch and push
- [ ] Step 9: keep this file updated throughout (ongoing)
- [ ] After sign-off: begin Phase 2 (Agent + Prompt Injection Defense)

## Key Decisions Made
- Package manager: **uv** — modern, fast, single tool for venv+deps+lockfile
- Embeddings: **local, open-source** (`sentence-transformers`,
  `all-MiniLM-L6-v2`) — free, deterministic, no API key needed
- LLM provider (Phase 1 default): **Ollama** (local, free, no API key) —
  user has no API credits currently; sits behind a provider-abstraction
  interface (`LLMProvider` ABC) so OpenAI/Gemini can be swapped in later
  via config only
- API style: **REST** (not GraphQL) — matches FastAPI's native style and
  the master doc's endpoint-by-endpoint framing; per-endpoint auth/policy
  checks are simpler to reason about for a security-focused project
- Dev infra: **Docker Compose from day one** — Postgres, Qdrant, Redis,
  Ollama all run as compose services from Phase 1 onward
- Authorization model for Phase 1: role-based via `allowed_roles` array
  column on `documents`, not a separate `permissions` join table —
  simpler for Phase 1, extendable to full ABAC in Phase 3's policy engine
  without a schema rewrite
- Golden rule: Qdrant vector similarity is a retrieval optimization only;
  every retrieved document is re-verified against Postgres
  (tenant_id + role) before its content reaches the LLM or the user

## Known Issues / Technical Debt
- The automated test suite fakes the vector store and LLM provider for
  determinism/speed — it never exercises the real `QdrantVectorStore`
  or `OllamaProvider` code paths. A real-Qdrant bug (`.search()` removed
  in qdrant-client 1.19, replaced by `.query_points()`) was only caught
  during manual end-to-end verification, not by `pytest`. Worth adding
  an integration-marked test against a live Qdrant container in a later
  phase. See `docs/phase-1-notes.md`.
- No rate limiting yet (planned Phase 5)
- No observability yet (planned Phase 5)

## How to resume in a new chat
Read this file top to bottom, then check `git log --oneline -20` for
recent commits. If Phase 1 status above still says "Not Started" or
"In Progress", read the Phase 1 plan context in this file's "Key
Decisions Made" section and confirm with the user before proceeding —
especially whether tests have been written yet (Step 3 requires explicit
go-ahead separate from plan approval).
