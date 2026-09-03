# Sentinel — Progress Log

## Current Phase
Phase 4 — DLP + Output Validation

## Status
Implementation complete, all 81 tests GREEN (including every Phase 1-3
test unchanged), manual end-to-end verification done. Awaiting your
manual review and sign-off before committing.

## Completed — Phases 1-3 (all merged to main)
- **Phase 1** (PR #1): JWT auth, tenant-isolated RAG, mandatory Postgres
  re-verification of every retrieved document. See `docs/phase-1-notes.md`.
- **Phase 2** (PR #2): LangGraph agent, indirect prompt-injection defense
  (retrieved documents wrapped as untrusted, system rules against
  following embedded instructions), 6 attack techniques tested
  before/after. See `docs/phase-2-notes.md`.
- **Phase 3** (PR #3): Tool Gateway + Policy/Risk Engine. Two tools
  (search_employee, create_ticket), deterministic ALLOW/DENY/
  REQUIRE_APPROVAL pipeline, human-approval loop. Spiked and rejected
  Needle (x86_64 build incompatibility). See `docs/phase-3-notes.md`.

## Completed — Phase 4
- [x] Phase 4 objective and plan produced and approved
- [x] Checked out `main`, pulled latest, branched
      `phase-4-dlp-output-validation`
- [x] Wrote 20 new tests first (TDD), confirmed RED
      (`ModuleNotFoundError: app.dlp.scanner`), then implemented to GREEN
- [x] Implemented:
  - `app/dlp/scanner.py` -- `scan_output()`: credentials always BLOCK,
    PII (email/phone) REDACT in place, salary figures REDACT for
    employees but ALLOW for HR/admin (role-aware, ties back to Phase 1).
    Findings are category labels only ("credential", "email", ...) --
    never the raw matched value
  - `app/agent/graph.py` -- new `dlp_check` node, added as the graph's
    final step before END. `AgentState` gained `answer_is_structured:
    bool`, set `True` by `handle_tool_request_node` for every message it
    writes itself (tool result, DENY, REQUIRE_APPROVAL). `dlp_check`
    only scans when that flag is absent -- exempting Phase 3's own
    controlled outputs from being redacted/broken by DLP
  - Logging: DLP events log `action` + `findings` (category labels) +
    `user_role` only -- verified via a log-capture test that the raw
    sensitive value never appears in logs
- [x] All 81 tests GREEN
- [x] Manual end-to-end verification against real Postgres + Qdrant +
      Ollama:
  - Confirmed `search_employee`'s legitimate email result survives
    DLP untouched (the Phase 3/4 exemption working live)
  - **Real finding:** adding tool definitions to every prompt (Phase 3)
    destabilized the small free model's plain RAG answers -- it started
    hallucinating tool calls for unrelated questions. Attempted a
    prompt-wording fix; it made things *worse* (broke the previously-
    reliable search_employee case too). Reverted to the original
    prompt. Documented as a known Phase 3 model-reliability limitation,
    resurfaced by Phase 4's testing -- not a Phase 4 defect, since DLP's
    own logic is pure deterministic regex, fully proven independent of
    the LLM via scripted fake-LLM tests. See `docs/phase-4-notes.md`.

## In Progress
- [ ] Your manual review — nothing committed until you sign off

## Next Steps
- [ ] User manual review and sign-off
- [ ] Write PR title/description, commit to
      `phase-4-dlp-output-validation`, open PR into `main`
- [ ] After merge: begin Phase 5 (Observability)

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
- Tool-calling format (Phase 3): a strict `TOOL_CALL: name(args)` text
  format, parsed defensively — malformed replies fall through to a safe
  plain answer, never a guessed action
- Tool security model (Phase 3): `user`/`db` context always
  server-injected from the authenticated session, never LLM-controlled
- Human-approval model (Phase 3): HIGH/CRITICAL-risk requests persisted
  as real `PENDING` rows; only admin decide via
  `POST /approvals/{id}/decide` executes them
- DLP scope (Phase 4): scans only the LLM's own freely-generated prose,
  never a tool's already-authorized result — implemented via an
  `answer_is_structured` flag set inside the graph, distinct from why
  `/approvals/decide` also skips DLP (that endpoint never touches the
  graph at all, so no flag is even involved there)
- DLP categories (Phase 4, focused set): credentials (BLOCK),
  PII/email/phone (REDACT), salary figures (role-aware REDACT/ALLOW) —
  generic "confidential" keyword matching deliberately excluded as too
  noisy for this phase

## Known Issues / Technical Debt
- The automated test suite fakes the vector store and LLM provider —
  real `QdrantVectorStore`/`OllamaProvider` bugs are only caught by
  manual end-to-end verification (see `docs/phase-1-notes.md`)
- `llama3.2:1b`'s tool-call triggering is unreliable and appears to
  worsen unpredictably with prompt-wording changes rather than improve
  (see `docs/phase-3-notes.md` and `docs/phase-4-notes.md`) — a
  known, documented model-capability gap. All failure modes observed so
  far fail safe (a confusing non-answer or a policy-correct denial),
  never an unintended action. **Deliberately deferred** (not
  forgotten) until a good working alternative is available — see the
  ranked options list in `docs/phase-3-notes.md`'s "Deferred" section
  (a free deterministic pre-router that only shows the AI the tool menu
  for tool-shaped questions is the top candidate; a bigger/paid model
  is a one-line config swap away once there's budget)
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
