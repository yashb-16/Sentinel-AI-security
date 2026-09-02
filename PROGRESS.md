# Sentinel — Progress Log

## Current Phase
Phase 3 — Tool Gateway + Policy/Risk Engine

## Status
Implementation complete, all 65 tests GREEN (including every Phase 1 and
Phase 2 test unchanged), manual end-to-end verification done against the
real stack. Awaiting your manual review and sign-off before committing.

## Completed — Phase 1 (merged to main via PR #1)
- JWT auth, tenant-isolated RAG, mandatory Postgres re-verification of
  every retrieved document (never trusting Qdrant alone). 16 tests.
  See `docs/phase-1-notes.md`.

## Completed — Phase 2 (merged to main via PR #2)
- LangGraph agent wrapping the retrieve→generate flow; every retrieved
  document wrapped as `<retrieved_document trust="untrusted">` with a
  system rule against following embedded instructions. 6 attack
  techniques tested before/after mitigation, verified live against a
  real poisoned document. See `docs/phase-2-notes.md`.

## Completed — Phase 3
- [x] Phase 3 objective and plan produced and approved
- [x] Checked out `main`, pulled latest, branched
      `phase-3-tool-gateway-policy-engine`
- [x] Spiked on Needle (Cactus Compute) as a dedicated tool-calling model
      to replace the structured-text-prompting workaround — found a real
      blocking incompatibility (their native build hard-codes ARM64
      compiler flags, fails on x86_64 Linux desktops) after getting an
      isolated Python 3.12 via `uv python install` (no system changes).
      Rejected for now; documented in `docs/phase-3-notes.md` so this
      isn't re-investigated from scratch later.
- [x] Wrote 29 new tests first (TDD), confirmed RED
      (`ModuleNotFoundError`), then implemented to GREEN: policy engine,
      risk engine, gateway, both tools, approvals endpoints, agent
      tool-calling, and a defense-in-depth test tying Phase 2 and 3
      together
- [x] Implemented:
  - `app/policy/{policy_engine,risk_engine,gateway}.py` — deterministic
    WHO/WHAT/WHICH policy rules, LOW/MEDIUM/HIGH/CRITICAL risk scoring,
    and the combined ALLOW/DENY/REQUIRE_APPROVAL gate
  - `app/tools/{search_employee,create_ticket,registry}.py` — tenant and
    identity are always server-injected from the authenticated session,
    never parsed from LLM-supplied arguments (removes an entire attack
    class by construction, not just by runtime check)
  - `app/db/models.py` — added `Ticket` and `ApprovalRequest`
  - `app/agent/graph.py` — extended with tool-request parsing
    (`TOOL_CALL: name(args)` strict format) and a
    `handle_tool_request_node` that routes every parsed request through
    the Gateway before anything executes
  - `app/api/routes_approvals.py` — `GET /approvals`,
    `POST /approvals/{id}/decide` (admin-only; approving actually runs
    the underlying tool)
- [x] All 65 tests GREEN
- [x] Manual end-to-end verification against real Postgres + Qdrant +
      Ollama (`llama3.2:1b`):
  - Employee self-lookup via `search_employee` — worked correctly, live
  - Employee attempting to look up someone else — correctly denied live
    by the real policy engine ("Sorry, that action is not allowed for
    your account")
  - Employee filing a salary-related ticket via natural language — the
    real model did **not** reliably format the multi-argument
    `create_ticket` tool call (see "Known Issues" below and
    `docs/phase-3-notes.md`) — confirmed **zero** side effects resulted
    (no Ticket, no ApprovalRequest), so the failure mode is a usability
    gap, not a security gap
  - Seeded a pending `ApprovalRequest` directly and verified the full
    human-approval loop for real: employee → 403 on `/approvals`, admin
    → sees it, admin approves → the real `Ticket` row gets created

## In Progress
- [ ] Your manual review — nothing committed until you sign off

## Next Steps
- [ ] User manual review and sign-off
- [ ] Write PR title/description, commit to
      `phase-3-tool-gateway-policy-engine`, open PR into `main`
- [ ] After merge: begin Phase 4 (DLP + Output Validation)

## Key Decisions Made
- Package manager: **uv**; Embeddings: local `sentence-transformers`;
  LLM default: **Ollama** (free/local, swappable via config); API style:
  **REST**; Dev infra: **Docker Compose**
- Authorization model: role-based `allowed_roles` on `documents`
- Golden rule (Phase 1): Qdrant is a performance filter only — every
  retrieved document is re-verified against Postgres before use
- Git workflow: `main` stays clean; every phase branches fresh from
  latest `main`, merges back via PR — never work directly on `main`
- Agent framework: **LangGraph**
- Prompt-injection defense (Phase 2): retrieved documents wrapped as
  `<retrieved_document trust="untrusted">` + explicit system rules
- Tool-calling format (Phase 3): a strict `TOOL_CALL: name(args)`
  text format the LLM is instructed to use, parsed defensively — an
  unrecognized/malformed reply always falls through to a safe plain
  answer, never a guessed action. Chosen over native function-calling
  APIs and over Needle (evaluated and rejected — see `docs/phase-3-notes.md`)
  because it needs zero extra dependencies and works with the existing,
  proven Ollama setup
- Tool security model (Phase 3): `user`/`db` context for every tool is
  always server-injected from the authenticated session, never parsed
  from LLM-supplied tool-call arguments — removes cross-tenant/identity
  forgery as an attack surface by construction rather than by runtime
  check alone
- Human-approval model (Phase 3): HIGH/CRITICAL-risk requests are
  persisted as real `PENDING` `ApprovalRequest` rows; only an admin
  deciding via `POST /approvals/{id}/decide` can let the underlying tool
  actually execute

## Known Issues / Technical Debt
- The automated test suite fakes the vector store and LLM provider —
  real `QdrantVectorStore`/`OllamaProvider` bugs are only caught by
  manual end-to-end verification (see `docs/phase-1-notes.md`)
- **New in Phase 3:** the real `llama3.2:1b` model does not reliably
  format multi-argument tool calls (`create_ticket`); single-argument
  calls (`search_employee`) worked reliably in live testing. This is a
  documented model-capability gap, not a security gap — malformed
  replies always fail safe (no tool executes) rather than executing
  something unintended. Revisit with a larger model or a
  purpose-built tool-calling model (Needle was evaluated and rejected
  for now due to an x86_64 build incompatibility) in a later phase.
- Phase 2's injection defense is only proven against 6 attack
  techniques and one small model manually — Phase 6 is reserved for
  broader adversarial red-teaming
- No rate limiting yet (planned Phase 5); no observability yet (planned
  Phase 5)
- No document ingestion pipeline or document-viewing endpoint yet
  (flagged in conversation as a real gap, not yet scheduled)

## How to resume in a new chat
Read this file top to bottom, then check `git log --oneline -20` for
recent commits and `git branch` for the current phase branch. If a
phase's status above still says "In Progress," confirm with the user
before proceeding — especially whether tests have been written yet
(writing tests requires explicit go-ahead separate from plan approval).
