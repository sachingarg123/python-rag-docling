from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import hashlib
import uuid
import csv

from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker import HierarchicalChunker
from hierarchical.postprocessor import ResultPostprocessor

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer


ROLE_TO_COLLECTIONS: dict[str, list[str]] = {
    "employee": ["general"],
    "finance": ["general", "finance"],
    "engineering": ["general", "engineering"],
    "marketing": ["general", "marketing"],
    "c_level": ["general", "finance", "engineering", "marketing"],
}

ALL_ROLES = list(ROLE_TO_COLLECTIONS.keys())


@dataclass(frozen=True)
class SourceDocument:
    path_or_url: str
    collection: str
    access_roles: list[str]


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _safe_page_number(doc_chunk) -> int | None:
    """Robustly extract page number from Docling chunk metadata."""
    # Try multiple paths: doc_items → prov → page_no, or direct page_no on chunk
    page_no = None
    
    # Path 1: Through doc_items and prov
    doc_items = getattr(doc_chunk.meta, "doc_items", None)
    if doc_items:
        for item in doc_items:
            prov = getattr(item, "prov", None)
            if prov:
                for p in prov:
                    candidate = getattr(p, "page_no", None)
                    if candidate is not None:
                        page_no = candidate
                        break
            if page_no is not None:
                break
    
    # Path 2: Direct chunk-level metadata
    if page_no is None:
        page_no = getattr(doc_chunk.meta, "page_number", None) or getattr(doc_chunk.meta, "page_no", None)
    
    # Path 3: Parent document metadata
    if page_no is None and hasattr(doc_chunk, "origin") and hasattr(doc_chunk.origin, "page_number"):
        page_no = getattr(doc_chunk.origin, "page_number", None)
    
    # Ensure page_no is an integer if found
    if page_no is not None:
        try:
            return int(page_no)
        except (ValueError, TypeError):
            pass
    
    return None


def _safe_chunk_type(doc_chunk) -> str:
    label = getattr(doc_chunk.meta, "label", None)
    if label:
        lowered = str(label).lower()
        if "table" in lowered:
            return "table"
        if "code" in lowered:
            return "code"
        if "heading" in lowered or "title" in lowered:
            return "heading"
    return "text"


def _section_title(doc_chunk) -> str:
    headings = getattr(doc_chunk.meta, "headings", None) or []
    if not headings:
        return "document_root"
    return headings[-1].strip() or "document_root"


def _section_parent_id(source_document: str, collection: str, section_title: str) -> str:
    return _stable_id(f"{source_document}|{collection}|{section_title}")


def _summarize_section(section_texts: list[str], max_chars: int = 500) -> str:
    joined = " ".join(t.strip() for t in section_texts if t and t.strip())
    if len(joined) <= max_chars:
        return joined
    # Lightweight summary fallback without additional LLM dependency.
    return joined[: max_chars - 3].rstrip() + "..."


def _chunks_from_csv(src: SourceDocument) -> list[dict]:
    path = Path(src.path_or_url)
    source_document = path.name
    section_title = "csv_rows"
    parent_chunk_id = _section_parent_id(source_document, src.collection, section_title)

    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, 1):
            # Keep a compact key=value representation so each row is searchable.
            content = " | ".join(
                f"{k}: {v}" for k, v in row.items() if k is not None and v is not None
            ).strip()
            if not content:
                continue

            rows.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "source_document": source_document,
                    "collection": src.collection,
                    "access_roles": src.access_roles,
                    "section_title": section_title,
                    "page_number": None,
                    "chunk_type": "table",
                    "parent_chunk_id": parent_chunk_id,
                    "chunk_level": "leaf",
                    "content": content,
                    "chunk_text": f"Row {row_idx}\n\n{content}",
                }
            )

    return rows


def parse_and_chunk(sources: Iterable[SourceDocument]) -> list[dict]:
    converter = DocumentConverter()
    # Explicitly configure chunker: max 512 tokens per chunk, 100 token overlap
    chunker = HierarchicalChunker(max_tokens=512, merge_short_chunks=True)

    all_leaf_chunks: list[dict] = []
    section_text_index: dict[str, list[str]] = {}

    for src in sources:
        suffix = Path(src.path_or_url).suffix.lower()
        if suffix == ".csv":
            try:
                csv_chunks = _chunks_from_csv(src)
                for payload in csv_chunks:
                    all_leaf_chunks.append(payload)
                    section_text_index.setdefault(payload["parent_chunk_id"], []).append(
                        payload["content"]
                    )
            except Exception as exc:
                print(f"⚠️  Warning: Failed to process CSV {src.path_or_url}: {exc}")
            continue

        try:
            result = converter.convert(src.path_or_url)
            # Only apply hierarchical postprocessor to PDFs; other formats may lack required metadata.
            if suffix == ".pdf":
                ResultPostprocessor(result).process()
            doc = result.document
        except Exception as exc:
            print(f"⚠️  Warning: Failed to parse document {src.path_or_url}: {exc}")
            continue

        source_document = Path(src.path_or_url).name if "/" in src.path_or_url else src.path_or_url
        if not source_document:
            source_document = getattr(doc, "name", "unknown_document")

        for doc_chunk in chunker.chunk(doc):
            content = doc_chunk.text.strip()
            if not content:
                continue

            section_title = _section_title(doc_chunk)
            parent_chunk_id = _section_parent_id(source_document, src.collection, section_title)
            chunk_type = _safe_chunk_type(doc_chunk)
            page_number = _safe_page_number(doc_chunk)

            headings = getattr(doc_chunk.meta, "headings", None) or []
            breadcrumb = " > ".join([h.strip() for h in headings if h and h.strip()])
            chunk_text = f"{breadcrumb}\n\n{content}" if breadcrumb else content

            payload = {
                "chunk_id": str(uuid.uuid4()),
                "source_document": source_document,
                "collection": src.collection,
                "access_roles": src.access_roles,
                "section_title": section_title,
                "page_number": page_number,
                "chunk_type": chunk_type,
                "parent_chunk_id": parent_chunk_id,
                "chunk_level": "leaf",
                "content": content,
                "chunk_text": chunk_text,
            }

            all_leaf_chunks.append(payload)
            section_text_index.setdefault(parent_chunk_id, []).append(content)

    parent_summary_chunks: list[dict] = []
    for leaf in all_leaf_chunks:
        parent_id = leaf["parent_chunk_id"]
        if any(c["chunk_id"] == parent_id for c in parent_summary_chunks):
            continue

        summary_text = _summarize_section(section_text_index[parent_id])
        parent_summary_chunks.append(
            {
                "chunk_id": parent_id,
                "source_document": leaf["source_document"],
                "collection": leaf["collection"],
                "access_roles": leaf["access_roles"],
                "section_title": leaf["section_title"],
                "page_number": leaf["page_number"],
                "chunk_type": "heading",
                "parent_chunk_id": None,
                "chunk_level": "parent_summary",
                "content": summary_text,
                "chunk_text": f"Section Summary: {leaf['section_title']}\n\n{summary_text}",
            }
        )

    return parent_summary_chunks + all_leaf_chunks


class DocumentAccessIndexService:
    def __init__(
        self,
        collection_name: str = "finsolve_component1",
        embedding_model: str = "all-MiniLM-L6-v2",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
    ) -> None:
        self.collection_name = collection_name
        self.embedder = SentenceTransformer(embedding_model)
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

    def recreate_collection(self) -> None:
        dim = self.embedder.get_sentence_embedding_dimension()
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def upsert_chunks(self, chunks: list[dict]) -> int:
        texts = [c["chunk_text"] for c in chunks]
        vectors = self.embedder.encode(texts, show_progress_bar=True)

        points = [
            PointStruct(id=idx, vector=vec.tolist(), payload=payload)
            for idx, (payload, vec) in enumerate(zip(chunks, vectors))
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    def ingest(self, sources: Iterable[SourceDocument]) -> int:
        chunks = parse_and_chunk(sources)
        self.recreate_collection()
        return self.upsert_chunks(chunks)

    def build_rbac_filter(
        self,
        user_role: str,
        route_collections: list[str] | None = None,
        chunk_level: str | None = None,
    ) -> Filter:
        """Build RBAC filter with optional chunk_level filtering.
        
        Args:
            user_role: User's role
            route_collections: Optional collection whitelist
            chunk_level: Optional filter for "leaf" (detailed) or "parent_summary" chunks
        """
        if user_role not in ROLE_TO_COLLECTIONS:
            raise ValueError(f"Unknown role: {user_role}")

        allowed_collections = ROLE_TO_COLLECTIONS[user_role]

        if route_collections:
            target = [c for c in route_collections if c in allowed_collections]
            if not target:
                raise PermissionError(
                    f"Role '{user_role}' cannot access requested collections: {route_collections}"
                )
        else:
            target = allowed_collections

        must_conditions = [
            FieldCondition(key="collection", match=MatchAny(any=target)),
            FieldCondition(key="access_roles", match=MatchValue(value=user_role)),
        ]
        
        # Add chunk_level filter if specified (prefer leaf chunks for detailed content)
        if chunk_level:
            must_conditions.append(
                FieldCondition(key="chunk_level", match=MatchValue(value=chunk_level))
            )

        return Filter(must=must_conditions)

    def retrieve(
        self,
        query: str,
        user_role: str,
        top_k: int = 10,
        route_collections: list[str] | None = None,
        min_similarity_score: float = 0.5,
        chunk_level: str | None = None,
    ) -> list[dict]:
        """Retrieve relevant chunks with improved filtering.
        
        Args:
            query: User's question
            user_role: User's role for RBAC
            top_k: Number of chunks to retrieve (increased to 10)
            route_collections: Optional collection filter
            min_similarity_score: Minimum cosine similarity threshold (0.5 filters low-quality matches)
            chunk_level: Filter by "leaf" (detailed) or "parent_summary" chunks
        """
        query_vector = self.embedder.encode(query).tolist()
        query_filter = self.build_rbac_filter(
            user_role=user_role,
            route_collections=route_collections,
            chunk_level=chunk_level,  # Add chunk_level to filter
        )

        # Retrieve more candidates to filter by similarity score
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=max(top_k * 2, 20),  # Fetch 2x to account for similarity filtering
            with_payload=True,
        )

        # Filter by similarity threshold and return top_k
        results = []
        for hit in hits.points:
            if hit.score >= min_similarity_score:  # Quality threshold
                results.append({**hit.payload, "score": round(hit.score, 4)})
                if len(results) >= top_k:
                    break
        
        return results
