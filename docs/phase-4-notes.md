# Phase 4 Notes

## Design decision: DLP only scans the AI's own raw prose, never a tool result

The most important call made before writing any code: if DLP blindly
scanned every answer, it would break Phase 3's own features. `search_employee`
exists specifically to return an email -- scanning that result for "PII"
and redacting it would make the tool useless.

Solution: `handle_tool_request_node` marks `answer_is_structured = True`
in the graph's state whenever it produces any message it wrote itself
(a tool result, a DENY message, a REQUIRE_APPROVAL notice). `dlp_check`
only scans when that flag is absent/false -- i.e. only when the answer is
something the LLM generated freely from retrieved documents. This is a
different mechanism from why `POST /approvals/{id}/decide` also skips
DLP -- that endpoint never touches the LangGraph agent at all, so there's
no flag involved there; DLP simply never gets a chance to run on that
code path in the first place. Both were discussed at length before
writing any tests, specifically to avoid confusing "flag says skip" with
"this code path doesn't go through the checkpoint at all."

## Real finding: adding tool definitions to every prompt destabilized plain RAG answers

Live testing surfaced something Phase 3's automated tests (which use
scripted fake LLMs) couldn't catch: once `TOOL_DEFINITIONS_PROMPT` is
part of *every* prompt (added in Phase 3), the real `llama3.2:1b` model
started hallucinating tool calls for completely unrelated questions.

Asking the plain question *"What is the Acme Vacation Policy?"* -- no
tool-related wording at all -- produced:
```
TOOL_CALL: search_employee(query="Acme Vacation Policy")
```
which the Policy Engine correctly denied (not the user's own email), so
the actual failure mode was **a confusing wrong answer, not a security
issue** -- but a wrong answer is still a real usability regression worth
fixing if possible.

**Attempted fix:** rewrote `TOOL_DEFINITIONS_PROMPT` with much more
explicit "ONLY use a tool when..." guardrail language. Result: **made it
worse.** The rewritten prompt caused the model to hallucinate a
malformed tool-call-shaped string for *every* question tried, including
the previously-reliable `search_employee` self-lookup case that had
worked cleanly in Phase 3's original live testing.

**Decision: reverted to the original, simpler prompt wording.** This
confirms (with concrete before/after evidence) what Phase 3's notes
already suspected: `llama3.2:1b`'s tool-triggering behavior is
fundamentally unstable, and iterating on prompt wording is closer to
whack-a-mole than a real fix at this model size. Chasing this further
would burn time for uncertain gains. Documented here rather than fixed,
matching Phase 3's decision to defer real reliability to a larger or
purpose-built tool-calling model in a later phase.

**Why this doesn't block Phase 4 specifically:** the DLP scanner itself
(`scan_output()`) is pure deterministic regex logic with zero dependency
on the LLM's reliability -- it was fully verified via 8 unit tests plus
graph-level and endpoint-level tests using scripted, controlled fake
LLMs, which is the correct way to prove DLP's own logic is right,
independent of whether the free local model can reliably decide *when*
to call a tool in the first place. The tool-triggering instability is a
Phase 3 concern that happened to surface more clearly during Phase 4's
live testing, not a Phase 4 defect.

## What was verified live, successfully

- `search_employee` explicitly requested by name -- worked correctly
  after the server was restarted to pick up code changes (a reminder to
  self: `uvicorn` without `--reload` needs a manual restart after any
  edit, including prompt-string changes in `registry.py`)
- All 81 automated tests (including 20 new Phase 4 tests) passed,
  covering: every DLP category's ALLOW/REDACT/BLOCK behavior, findings
  never containing the raw sensitive value, the exemption for
  tool-originated answers, and an end-to-end log-capture test proving a
  leaked credential's raw value never appears in application logs (only
  the category label "credential" does)
