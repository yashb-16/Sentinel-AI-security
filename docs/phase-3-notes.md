# Phase 3 Notes

## Spike: evaluated Needle (Cactus Compute) for tool-call parsing, rejected it

Before committing to the "strict structured-text-prompting" workaround for
tool-calling with a tiny free LLM, we spiked on **Needle** -- a
26M-45M-parameter model from Cactus Compute, specifically distilled from
Gemini for reliable on-device function-calling. It looked like a direct
fix for the exact weakness `llama3.2:1b` has (unreliable structured
output for tool requests).

The spike found a real, blocking incompatibility, not just friction:

1. `pip install cactus-compute` works fine.
2. `cactus serve <model>` fails -- the PyPI package doesn't ship a
   pre-built native engine; it wants you to run `cactus build --python`.
3. `cactus build` requires a full git clone of their repo (not just the
   pip package) and, per their own setup script, **specifically Python
   3.12** (we initially only had 3.10).
4. Got Python 3.12 cleanly via `uv python install 3.12` (no system
   changes, no sudo) and re-ran their setup successfully.
5. `cactus build --python` then failed with:
   `cc1plus: error: bad value ('armv8.2-a+fp16+simd+dotprod+i8mm') for
   '-march=' switch` -- their native C++ build hard-codes **ARM64**
   compiler flags (Apple Silicon / mobile chips), and doesn't fall back
   correctly on an **x86_64** Linux desktop, which is what this
   machine (and most dev/server Linux boxes) actually is.

That's a genuine architecture-level incompatibility in a very new
(weeks-old) project that's mobile/edge-first by design, not something
fixable by installing one more dependency. Decision: stuck with the
Ollama-based structured-text-prompting approach instead. Worth
revisiting Needle later if it matures and adds proper x86_64 desktop
support -- noted here so we don't re-litigate the same investigation from
scratch in a future phase.

## Real finding: the small model is unreliable at multi-argument tool calls

Live verification against the real `llama3.2:1b` produced a genuinely
useful, honest result -- not a uniform success story:

- **`search_employee(query="...")`** (one argument) -- the model
  formatted the `TOOL_CALL: ...` line correctly every time it was tried,
  and both the "search yourself" (allowed) and "search someone else"
  (policy-denied) cases worked exactly as designed, live, against the
  real Postgres-backed policy engine.
- **`create_ticket(subject, description, category)`** (three arguments)
  -- the model did **not** reliably produce the exact required format.
  It would reply with things like:
  ```
  TOOL_CALL: create_ticket

  Since I don't have any specific information about the subject,
  description, or category for the create_ticket tool, I will not be
  able to create a ticket.
  ```
  which doesn't match the strict `TOOL_CALL: name(args)` pattern, so
  `parse_tool_call()` correctly returned `None` for it.

**Why this is a real limitation, not a bug we introduced:** it's exactly
the small-model unreliability problem this whole design was built to be
safe against -- and confirms it's a real, live phenomenon, not a
hypothetical one we invented to justify the Needle spike.

**Why this is NOT a security failure:** verified directly against the
database after these malformed replies -- zero `Ticket` rows, zero
`ApprovalRequest` rows were created. The agent's fallback behavior held
exactly as designed: if the reply doesn't match the strict tool-call
pattern, it's treated as a plain answer and nothing executes. A confusing
answer is a usability problem; a silently-executed unintended action
would have been a security problem. This design only ever produced the
former.

**What this means going forward:** the REQUIRE_APPROVAL flow (Policy →
Risk → Gateway → pending record → admin decide → real execution) was
still fully verified end-to-end against the real database and real
`/approvals` endpoints -- just by seeding one pending request directly
rather than relying on the flaky model to produce a well-formed
multi-argument tool call on demand. The mechanism is proven; getting the
free local model to reliably *trigger* it for multi-argument tools is a
known, documented gap, not a hidden one. Worth revisiting with a larger
or purpose-built tool-calling model in a later phase (see PROGRESS.md).

## Design note: tenant/identity are never LLM-controlled parameters

`search_employee` and `create_ticket` both take `user` and `db` as
keyword-only arguments supplied entirely by our own code from the
authenticated session -- never parsed out of the LLM's tool-call text.
This was a deliberate choice made during planning, not something added
reactively: it removes an entire class of attack (a compromised or
tricked LLM trying to forge a different tenant_id or a different
"acting as" user) by construction, rather than relying on a runtime
check to catch it after the fact. The defense-in-depth test
(`test_defense_in_depth_malicious_tool_request.py`) still proves the
Gateway independently blocks a forbidden request regardless of intent,
but the *tenant/identity* attack surface specifically doesn't exist at
all here, which is a stronger guarantee than "we checked for it and
caught it."
