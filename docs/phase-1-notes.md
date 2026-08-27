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

## Known limitation carried forward

The automated test suite fakes both the vector store and the LLM
provider for determinism and speed (no network, no model downloads
required to run `pytest`). This means real `QdrantVectorStore` /
`OllamaProvider` wiring bugs (like the `.search()` removal above) are
only caught by manual end-to-end verification, not by `pytest`. Worth
revisiting in a later phase — e.g. a slow/integration-marked test that
exercises the real Qdrant client against a running container in CI.
