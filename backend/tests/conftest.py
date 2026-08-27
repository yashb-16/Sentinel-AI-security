"""Shared fixtures: an isolated test database, seeded tenants/users/documents,
a fake in-memory vector store (no real Qdrant needed for tests), and a fake
LLM provider so tests are deterministic and don't require Ollama/API keys.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Document, Role, Tenant, User
from app.auth.security import hash_password

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def seeded(db_session):
    """Seeds two tenants, each with an employee/hr/admin user and a mix of
    general + hr_confidential documents. Returns a dict of everything a test
    might need, keyed by descriptive name.
    """
    acme = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme")
    globex = Tenant(id=uuid.uuid4(), name="Globex Corp", slug="globex")
    db_session.add_all([acme, globex])
    db_session.flush()

    def make_user(tenant, role, email):
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password("password123"),
            role=role,
        )
        db_session.add(user)
        return user

    acme_employee = make_user(acme, Role.EMPLOYEE, "employee@acme-corp.dev")
    acme_hr = make_user(acme, Role.HR, "hr@acme-corp.dev")
    acme_admin = make_user(acme, Role.ADMIN, "admin@acme-corp.dev")
    globex_employee = make_user(globex, Role.EMPLOYEE, "employee@globex-corp.dev")
    globex_hr = make_user(globex, Role.HR, "hr@globex-corp.dev")

    def make_doc(tenant, title, content, classification, allowed_roles):
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title=title,
            content=content,
            classification=classification,
            allowed_roles=allowed_roles,
            qdrant_point_id=uuid.uuid4(),
        )
        db_session.add(doc)
        return doc

    acme_general_doc = make_doc(
        acme,
        "Acme Vacation Policy",
        "Acme employees get 20 days of paid vacation per year.",
        "general",
        ["employee", "hr", "admin"],
    )
    acme_hr_doc = make_doc(
        acme,
        "Acme Salary Bands",
        "Acme engineering salary band L4 is 140000 to 170000 USD.",
        "hr_confidential",
        ["hr", "admin"],
    )
    globex_general_doc = make_doc(
        globex,
        "Globex Vacation Policy",
        "Globex employees get 15 days of paid vacation per year.",
        "general",
        ["employee", "hr", "admin"],
    )
    globex_hr_doc = make_doc(
        globex,
        "Globex Salary Bands",
        "Globex engineering salary band L4 is 130000 to 160000 USD.",
        "hr_confidential",
        ["hr", "admin"],
    )

    db_session.commit()

    return {
        "tenants": {"acme": acme, "globex": globex},
        "users": {
            "acme_employee": acme_employee,
            "acme_hr": acme_hr,
            "acme_admin": acme_admin,
            "globex_employee": globex_employee,
            "globex_hr": globex_hr,
        },
        "documents": {
            "acme_general": acme_general_doc,
            "acme_hr": acme_hr_doc,
            "globex_general": globex_general_doc,
            "globex_hr": globex_hr_doc,
        },
    }


class FakeVectorStore:
    """Stands in for Qdrant in tests. Ignores real embeddings and instead
    does naive keyword-overlap matching across ALL seeded documents,
    regardless of tenant -- deliberately over-broad, so tests prove the
    retriever's Postgres re-verification step (not the vector store) is
    what enforces tenant/role isolation.
    """

    def __init__(self, db_session):
        self._db_session = db_session

    def search(self, *, vector, query_text: str, tenant_id: str, top_k: int = 5):
        from app.db.models import Document
        from app.rag.retriever import VectorHit

        query_words = set(query_text.lower().split())
        hits = []
        for doc in self._db_session.query(Document).all():
            doc_words = set(doc.content.lower().split()) | set(doc.title.lower().split())
            if query_words & doc_words:
                hits.append(
                    VectorHit(
                        doc_id=doc.id,
                        tenant_id=doc.tenant_id,
                        allowed_roles=doc.allowed_roles,
                    )
                )
        return hits[:top_k]


class FakeEmbedder:
    def embed(self, text: str):
        return [0.0] * 8


@pytest.fixture()
def client(db_session, monkeypatch):
    """A TestClient wired to the test db_session, a fake LLM provider, and a
    fake vector store, so /ask tests don't need real Ollama/Qdrant/embedding
    infrastructure and stay fully deterministic.
    """
    from app.main import app
    from app.db import base as db_base
    from app.rag import llm as llm_module
    from app.rag import retriever as retriever_module

    def override_get_db():
        yield db_session

    app.dependency_overrides[db_base.get_db] = override_get_db

    class FakeLLMProvider:
        def generate(self, prompt: str) -> str:
            return "FAKE ANSWER based on provided context."

    monkeypatch.setattr(llm_module, "get_llm_provider", lambda: FakeLLMProvider())
    monkeypatch.setattr(retriever_module, "get_vector_store", lambda: FakeVectorStore(db_session))
    monkeypatch.setattr(retriever_module, "get_embedder", lambda: FakeEmbedder())

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def login(client, email: str, password: str = "password123") -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
