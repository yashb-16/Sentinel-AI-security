"""SECURITY: the retriever must never trust a vector store hit's own claimed
tenant_id/allowed_roles. It must re-fetch the document from Postgres and
authorize against the real row -- proving the "Qdrant filter is a
performance optimization, never the authorization decision" control
actually executes.
"""

from app.rag.retriever import VectorHit, retrieve_documents


class MismatchedVectorStore:
    """Simulates a misconfigured/compromised Qdrant: returns hits whose
    payload tenant_id/allowed_roles do not match what's really in Postgres
    for that doc_id, and also returns hits for documents outside the
    querying tenant entirely.
    """

    def __init__(self, hits):
        self._hits = hits

    def search(self, *, vector, query_text: str, tenant_id: str, top_k: int = 5):
        return self._hits


def test_hit_claiming_wrong_tenant_is_dropped(seeded, monkeypatch, db_session):
    from app.rag import retriever as retriever_module

    globex_doc = seeded["documents"]["globex_general"]
    acme_employee = seeded["users"]["acme_employee"]

    # Payload lies: claims this Globex doc belongs to Acme and is allowed
    # for employees. The real Postgres row says otherwise.
    forged_hit = VectorHit(
        doc_id=globex_doc.id,
        tenant_id=acme_employee.tenant_id,
        allowed_roles=["employee", "hr", "admin"],
    )
    monkeypatch.setattr(
        retriever_module, "get_vector_store", lambda: MismatchedVectorStore([forged_hit])
    )
    monkeypatch.setattr(retriever_module, "get_embedder", lambda: FakeEmbedder())

    results = retrieve_documents(question="anything", user=acme_employee, db=db_session)

    assert globex_doc.id not in {doc.id for doc in results}


def test_hit_claiming_wrong_allowed_roles_is_dropped(seeded, monkeypatch, db_session):
    from app.rag import retriever as retriever_module

    acme_hr_doc = seeded["documents"]["acme_hr"]
    acme_employee = seeded["users"]["acme_employee"]

    # Payload lies: claims this hr_confidential doc is allowed for employees.
    # The real Postgres row only allows hr/admin.
    forged_hit = VectorHit(
        doc_id=acme_hr_doc.id,
        tenant_id=acme_employee.tenant_id,
        allowed_roles=["employee", "hr", "admin"],
    )
    monkeypatch.setattr(
        retriever_module, "get_vector_store", lambda: MismatchedVectorStore([forged_hit])
    )
    monkeypatch.setattr(retriever_module, "get_embedder", lambda: FakeEmbedder())

    results = retrieve_documents(question="anything", user=acme_employee, db=db_session)

    assert acme_hr_doc.id not in {doc.id for doc in results}


def test_hit_pointing_to_nonexistent_document_is_dropped(seeded, monkeypatch, db_session):
    import uuid

    from app.rag import retriever as retriever_module

    acme_employee = seeded["users"]["acme_employee"]
    forged_hit = VectorHit(
        doc_id=uuid.uuid4(),
        tenant_id=acme_employee.tenant_id,
        allowed_roles=["employee"],
    )
    monkeypatch.setattr(
        retriever_module, "get_vector_store", lambda: MismatchedVectorStore([forged_hit])
    )
    monkeypatch.setattr(retriever_module, "get_embedder", lambda: FakeEmbedder())

    results = retrieve_documents(question="anything", user=acme_employee, db=db_session)

    assert results == []


class FakeEmbedder:
    def embed(self, text: str):
        return [0.0] * 8
