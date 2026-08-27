# Phase 1 Notes

## Issue: SQLite in-memory + FastAPI's threadpool silently gave tests an empty database

`TestClient` runs FastAPI request handlers inside `anyio`'s worker
threadpool, not the thread that set up the test fixtures. `create_engine`
for `sqlite:///:memory:` defaults to `SingletonThreadPool`, which hands
out a *different* connection (and therefore a different, empty in-memory
database) per thread. Every `/ask` and `/auth/login` test failed with
`no such table: users`, even though the fixture had just created and
seeded the schema moments earlier on the main thread.

Fix: explicitly pass `poolclass=StaticPool` when creating the test
engine, so every thread shares the single in-memory connection. This is
a well-known SQLAlchemy + SQLite gotcha that's easy to hit the first time
a test suite combines an in-memory DB with any kind of threaded test
client.

## Issue: `str(SomeStrEnum.MEMBER)` doesn't return the enum's value

`Role` is defined as `class Role(str, enum.Enum)`. Intuitively,
`str(Role.HR)` should return `"hr"` since `Role.HR` *is* a string
instance under the hood — but `enum.Enum`'s `__str__` override takes
precedence and returns `"Role.HR"` instead. This only surfaced when a
`User` object was queried through the *same* SQLAlchemy session that
created it (via the identity map returning the original in-memory
`Role.HR` object rather than round-tripping through the DB as plain
text) — the JWT then carried `"role": "Role.HR"` instead of `"role":
"hr"`. A single test (`test_login_jwt_contains_expected_claims`) caught
it immediately.

Fix: added an explicit `__str__` returning `self.value` to `Role`. This
also protects against the same class of bug anywhere else `str(role)` is
called on an in-memory enum instance rather than a DB-round-tripped
value.

## Issue: reserved TLDs (`.test`) rejected by `email-validator`

Seed/test fixtures originally used `employee@acme.test` per the common
convention of using `example.com`/`.test` for fake data. Pydantic's
`EmailStr` (via `email-validator`) actively rejects RFC 2606 reserved
names (`.test`, `.example`, `.invalid`, `.localhost`, `example.com`,
etc.) as "special-use" domains — this isn't a deliverability check, it's
baked into the syntax validator itself. Switched fixtures to invented,
non-reserved domains (`acme-corp.dev`, `globex-corp.dev`) instead.

## Issue: `qdrant-client` 1.19 removed `QdrantClient.search()`

Newer `qdrant-client` versions deprecated `.search()` in favor of
`.query_points()`, which returns a `QueryResponse` wrapping `.points`
instead of a bare list of hits. This only surfaced during manual
end-to-end verification against a real Qdrant container — the test
suite uses a fake vector store and never touches the real client, which
is a known gap (see "Known limitation" below).

## Issue: port conflicts with a pre-existing native Ollama/Redis on the dev machine

The dev machine already had Ollama and Redis running natively on ports
11434 and 6379. `docker compose up` for those two services failed with
"address already in use". Not a project bug — verification proceeded
against the native Ollama instance instead (pulled `llama3.2:1b`
directly via `ollama pull`). On a clean machine, `docker-compose.yml`'s
Ollama/Redis services would bind those ports without conflict.

## Issue: orphan `main` branch had no shared history with the feature branch, blocking the PR

The repo started with zero commits, and `phase-1-auth-rag` was pushed
before `main` existed anywhere (locally or on GitHub) — so GitHub quietly
made `phase-1-auth-rag` the default branch. To get a proper `main` in
place, it was created via `git checkout --orphan main` + an empty
"Initial commit". That fixed the missing-branch symptom, but orphan
branches are *deliberately* disconnected from all other history — so
`main` and `phase-1-auth-rag` ended up as two unrelated root commits in
the same repo.

That broke pull request creation outright:
`gh pr create` failed with `GraphQL: The phase-1-auth-rag branch has no
history in common with main` — GitHub requires two branches to share a
common ancestor before it can diff/merge them; it's not just a UI quirk,
the API rejects it too.

Fix: `git rebase --onto main --root phase-1-auth-rag` — replays
`phase-1-auth-rag`'s commit on top of `main`'s initial commit instead of
leaving it as a separate root, giving them real shared ancestry. Content
was verified byte-identical before and after (`git diff <old-sha>
phase-1-auth-rag` was empty). Required `git push --force-with-lease` to
publish, since rebasing changes the commit's hash even though nothing
inside it changed. Also set `main` back as the repo's default branch on
GitHub (`gh repo edit --default-branch main`), since the earlier
first-push-wins default had picked `phase-1-auth-rag` instead.

Also fixed along the way: initially tried to restore untracked files by
switching back to `phase-1-auth-rag` right after creating `main`, and
Git refused ("untracked working tree files would be overwritten") since
`main`'s empty index had left Phase 1's files on disk but untracked.
Verified they were still byte-identical to what was already safely
committed on `phase-1-auth-rag` before force-checking out — nothing was
at risk, but worth remembering that switching away from a branch whose
index you just emptied needs that same care.

**Lesson for next time:** when bootstrapping a brand-new repo, create and
push `main` (even just an empty "Initial commit") *first*, before any
feature branch — not after. Creating a feature branch first and
retrofitting `main` afterward is exactly what produced the disconnected
history here.

## Known limitation carried forward

The automated test suite fakes both the vector store and the LLM
provider for determinism and speed (no network, no model downloads
required to run `pytest`). This means real `QdrantVectorStore` /
`OllamaProvider` wiring bugs (like the `.search()` removal above) are
only caught by manual end-to-end verification, not by `pytest`. Worth
revisiting in a later phase — e.g. a slow/integration-marked test that
exercises the real Qdrant client against a running container in CI.
