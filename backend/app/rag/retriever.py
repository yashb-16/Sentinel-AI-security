from sqlalchemy.orm import Session

from app.db.models import Document, User
from app.rag.embeddings import get_embedder
from app.rag.qdrant_store import VectorHit, get_vector_store

__all__ = ["VectorHit", "retrieve_documents", "get_embedder", "get_vector_store"]


def retrieve_documents(*, question: str, user: User, db: Session, top_k: int = 5) -> list[Document]:
    """Retrieves documents relevant to `question` that `user` is actually
    authorized to see.

    Qdrant's tenant_id filter (applied inside the vector store) is a
    performance optimization only. The authorization decision is made here,
    by re-fetching every candidate document from PostgreSQL and checking its
    real tenant_id and allowed_roles -- never trusting the vector store's
    claimed payload.
    """
    embedder = get_embedder()
    vector = embedder.embed(question)

    store = get_vector_store()
    hits = store.search(vector=vector, query_text=question, tenant_id=str(user.tenant_id), top_k=top_k)

    verified_documents: list[Document] = []
    for hit in hits:
        doc = db.get(Document, hit.doc_id)
        if doc is None:
            continue
        if str(doc.tenant_id) != str(user.tenant_id):
            continue
        if str(user.role) not in doc.allowed_roles:
            continue
        verified_documents.append(doc)

    return verified_documents
