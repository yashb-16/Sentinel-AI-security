# Benchmarks

How well do Sentinel's security layers actually work? This page records what was measured, on
what data, what the numbers mean, and where they stop meaning anything. Everything here is
reproducible from the scripts in `backend/scripts/`.

## Summary

| Layer | Measurement | Result |
|-------|-------------|--------|
| DLP (output scanning) | Recall on independent data, before → after hardening | **39.4% → 94.0%** (810 cases) |
| DLP | False positives on 2,839 real prose sentences, before → after | 0 → 3 (**0.1%**) |
| DLP | Latency per scan | ~10 µs (single string, one machine) |
| Prompt-injection defense | 60 real attacks × 2 small LLMs | Both models already resisted (≤3.3% obeyed); defense effect **not measurable** |
| Tool Gateway | 18 hand-written policy cases | 18/18, 0 unsafe auto-allows (regression check, **not** independent evidence) |
| Test suite | `pytest` | 111 tests pass (81 before this work + 30 new DLP cases) |

## Why the benchmark uses independent data

The first benchmark (`benchmark.py`) used test cases written by the same person who wrote the
code, so it reported 100% — which proves nothing (the test author already knew what the code
handles). `benchmark_independent.py` replaces that with data we did not write:

- **Emails/phones:** [Faker](https://faker.readthedocs.io), 7 locales (en_US, en_GB, en_IN, de_DE, fr_FR, ja_JP, es_ES), 30 each.
- **Secrets:** random strings following each vendor's public key format (AWS, OpenAI legacy and project, GitHub, Stripe, Google, Slack, JWT), 40 each.
- **Salary:** 70 amounts across 7 currency/notation formats.
- **False positives:** 2,839 random sentences from Python's own language reference (`pydoc_data.topics`).
- **Injection attacks:** English `label=1` samples from the public [`deepset/prompt-injections`](https://huggingface.co/datasets/deepset/prompt-injections) dataset.

Seeds are fixed, and every rate carries a 95% Wilson confidence interval.

## DLP: measure → find gaps → fix → re-measure

**Baseline (original scanner):** 319/810 = **39.4%** recall. It was precise but narrow:

| Category | Before | After |
|----------|--------|-------|
| Email (7 locales) | 210/210 | 210/210 |
| Phone (7 locales) | 10/210 (4.8%) | 161/210 (76.7%) |
| AWS `AKIA…`, OpenAI legacy `sk-…` | 40/40 each | 40/40 each |
| OpenAI `sk-proj-…`, GitHub, Stripe, Google, Slack, JWT | **0/40 each** | **40/40 each** |
| Salary (7 formats) | 19/70 (27.1%) | 70/70 (100%) |
| **Overall** | **319/810 (39.4%)** | **761/810 (94.0%, CI 92–95%)** |

**What changed** (`backend/app/dlp/scanner.py`, tests first — 20 new tests failed before the fix, all pass after):
extra credential formats; a phone candidate finder plus a filter (`_is_phone`) instead of one US-only regex;
salary detection for `£ € ¥`, `USD/INR/Rs`, `k`, `dollars`, `LPA`.

**The trade-off (be upfront about it):** false positives went from 0/2,839 to 3/2,839 (0.1%). All three
are digit tables/code samples in the Python docs (e.g. a binary/hex table), not prose. Wider phone
matching costs a little precision; that is the price of catching international formats.

**Remaining gaps (documented in code as a `ponytail:` note):** 49 phone misses, almost all bare
unseparated 10-digit numbers (`9656672993`) and a few UK/German bracket formats. Bare digit runs are
deliberately not flagged, because order IDs and timestamps look identical. The upgrade path is the
`phonenumbers` library if this ever matters. Also untested: names, addresses, government IDs, non-Latin scripts.

## Prompt injection: an honest null result

60 attack payloads (dataset phrasing + an appended canary instruction, so "obeyed" is machine-checkable),
1 run each, against real local models. "Obeyed" = the reply is essentially only the canary.
"Mentioned" = the canary appears at all (usually the model *describing* the document, not obeying it).

| Model | Prompt | Obeyed | Mentioned |
|-------|--------|--------|-----------|
| llama3.2:1b | naive | 2/60 (3.3%) | 5/60 (8.3%) |
| llama3.2:1b | production (wrap + rules + tool menu) | 2/60 (3.3%) | 11/60 (18.3%) |
| qwen2.5:0.5b | naive | 1/60 (1.7%) | 7/60 (11.7%) |
| qwen2.5:0.5b | production | 0/60 (0%) | 16/60 (26.7%) |

**Reading:** both models already ignore almost all of these attacks with no defense, so there is no
headroom to show the defense helping. The 1–2 case differences are within noise at n=60. The larger
"mentioned" numbers under the production prompt mean the model quotes the injected text more often when
it is wrapped — it is not obeying it. **We do not claim the defense reduces attack success on real
models.** The earlier "6/6 attacks blocked" tests (`test_prompt_injection_attacks.py`) run against a
scripted, deliberately gullible fake LLM: they prove the wrapping logic behaves as designed, not that a
real model is safer.

The way to measure this properly is a more susceptible model and a larger, harder attack set (Phase 6 red-teaming).

## Tool Gateway

18 policy cases (role × tool × arguments → ALLOW / DENY / REQUIRE_APPROVAL) all match, with 0 cases
that should have needed approval or denial being auto-allowed. These cases were written from the
code's intended behavior, so this is a **regression guard**, not independent validation.

## Limitations (all of them)

- Faker data and vendor-format strings are a proxy for real leaked data.
- Salary detection is keyword-gated ("salary", "pay", "ctc", "compensation") plus amount format.
- Latency is one string on one laptop, not load-tested; there are no throughput or concurrency numbers.
- LLM results use 0.5B–1B parameter local models, not production-grade models, and n=60 per cell.
- The DLP scanner is regex-based: high precision, bounded recall by design.

## Reproduce

```bash
uv run python backend/scripts/benchmark.py --skip-llm          # hand-written cases (regression)
curl -sL -o pi.parquet https://huggingface.co/api/datasets/deepset/prompt-injections/parquet/default/train/0.parquet
ollama pull qwen2.5:0.5b                                        # llama3.2:1b already used elsewhere
uv run --with faker --with pandas --with pyarrow python backend/scripts/benchmark_independent.py --pi-parquet pi.parquet
```

## Talking points

- **"How do you know it works?"** First benchmark was self-written and scored 100% — I recognized that as circular, rebuilt it on third-party data, and the real number was 39%.
- **"What did you do about it?"** Wrote failing tests for each gap, fixed the scanner, re-measured on the same seeded data: 39% → 94%, at a cost of 0.1% false positives.
- **"Did the injection defense work?"** Not measurably — the small models already resisted. I report that as-is instead of claiming a win, and know what experiment would settle it.
- **"Why regex, not ML?"** Deterministic, ~10 µs, auditable, and never logs the matched value. Trade-off: bounded recall; upgrade path is `phonenumbers` / Presidio.
