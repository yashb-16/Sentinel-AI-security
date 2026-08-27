"""CLI entry point: seeds PostgreSQL with demo tenants/users/documents and
upserts matching vectors into Qdrant. Run after `alembic upgrade head`.

Usage: uv run python -m backend.scripts.seed_data
"""

from app.config import get_settings
from app.db.base import SessionLocal
from app.db.models import Document
from app.db.seed import seed_all
from app.rag.embeddings import get_embedder
from app.rag.qdrant_store import get_vector_store


def main() -> None:
    db = SessionLocal()
    try:
        seed_all(db)

        settings = get_settings()
        embedder = get_embedder()
        store = get_vector_store()
        store.ensure_collection(vector_size=len(embedder.embed("dimension probe")))

        for doc in db.query(Document).all():
            vector = embedder.embed(f"{doc.title}\n{doc.content}")
            store.upsert(
                point_id=doc.qdrant_point_id,
                vector=vector,
                tenant_id=doc.tenant_id,
                doc_id=doc.id,
                allowed_roles=doc.allowed_roles,
            )

        print(f"Seeded {db.query(Document).count()} documents into Postgres and "
              f"Qdrant collection '{settings.qdrant_collection}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
