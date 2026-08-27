import uuid
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings


@dataclass
class VectorHit:
    doc_id: uuid.UUID
    tenant_id: uuid.UUID
    allowed_roles: list[str]


class QdrantVectorStore:
    """Thin wrapper around Qdrant: filters candidates by tenant_id at query
    time as a performance optimization. This filter is NEVER treated as an
    authorization decision -- the retriever always re-verifies every hit
    against PostgreSQL before using it.
    """

    def __init__(self, url: str, collection: str):
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url)
        self._collection = collection

    def ensure_collection(self, vector_size: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def upsert(self, *, point_id: uuid.UUID, vector: list[float], tenant_id: uuid.UUID,
               doc_id: uuid.UUID, allowed_roles: list[str]) -> None:
        from qdrant_client.models import PointStruct

        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=str(point_id),
                    vector=vector,
                    payload={
                        "doc_id": str(doc_id),
                        "tenant_id": str(tenant_id),
                        "allowed_roles": allowed_roles,
                    },
                )
            ],
        )

    def search(self, *, vector: list[float], query_text: str, tenant_id: str, top_k: int = 5):
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        response = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=Filter(
                must=[FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id)))]
            ),
            limit=top_k,
        )
        return [
            VectorHit(
                doc_id=uuid.UUID(hit.payload["doc_id"]),
                tenant_id=uuid.UUID(hit.payload["tenant_id"]),
                allowed_roles=hit.payload["allowed_roles"],
            )
            for hit in response.points
        ]


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    settings = get_settings()
    return QdrantVectorStore(settings.qdrant_url, settings.qdrant_collection)
