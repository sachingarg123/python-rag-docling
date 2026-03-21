import os
import getpass
from pathlib import Path
from dotenv import load_dotenv

from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker import HierarchicalChunker
from hierarchical.postprocessor import ResultPostprocessor

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from groq import Groq

# Load .env from the same folder as this script to avoid CWD-dependent behavior.
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


SOURCE = "https://raw.githubusercontent.com/tnahddisttud/sample-doc/refs/heads/main/AtliqAI_HR_Policies.pdf"

# Load the document using Docling and convert it into a structured format.
def load_document(source: str):
    """
    Parse a PDF using Docling.
    Returns a DoclingDocument object — not a plain string.
    """
    converter = DocumentConverter()
    result = converter.convert(source)
    ResultPostprocessor(result).process()
    return result.document

doc = load_document(SOURCE)
print(f"Document loaded: {doc.name}")

markdown_doc = doc.export_to_markdown()

print(markdown_doc[:1000])

# Chunk the document using Docling's HierarchicalChunker.
chunker   = HierarchicalChunker()
doc_chunks = list(chunker.chunk(doc))

print(f"Total chunks: {len(doc_chunks)}")

# Inspect a raw DocChunk
sample = doc_chunks[2]
print(f"headings : {sample.meta.headings}")
print(f"text     : {sample.text[:200]}…")


# Convert DocChunks into plain dicts with the fields we care about.
def convert_chunk(doc_chunk) -> dict:
    """
    Convert a Docling DocChunk into a plain dict.

    headings   → list preserved as-is
    content    → paragraph text
    chunk_text → breadcrumb + content  (what gets embedded)
    """
    headings   = doc_chunk.meta.headings or []
    content    = doc_chunk.text.strip()
    breadcrumb = " > ".join(headings)
    chunk_text = f"{breadcrumb}\n\n{content}" if breadcrumb else content

    return {
        "headings":   headings,
        "content":    content,
        "chunk_text": chunk_text,
    }

chunks = [convert_chunk(c) for c in doc_chunks]

for chunk in chunks[:3]:
    print("─" * 60)
    print(f"headings   : {chunk['headings']}")
    print(f"content    : {chunk['content'][:200]}…")

# Embed the chunks using Sentence Transformers
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
embedder = SentenceTransformer(EMBEDDING_MODEL)

chunk_texts = [c["chunk_text"] for c in chunks]

print(f"Embedding {len(chunk_texts)} chunks …")
embeddings = embedder.encode(chunk_texts, show_progress_bar=True)

print(f"Shape: {embeddings.shape}")

# Index the chunks and their embeddings into Qdrant
client = QdrantClient(host="localhost", port=6333)
COLLECTION_NAME = "pdf-hr-policies"
DIM = embedder.get_sentence_embedding_dimension()

client.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=DIM,
        distance=Distance.COSINE,
    ),
)
print("Collection created.")

points = [
    PointStruct(
        id=idx,
        vector=embedding.tolist(),
        payload={
            "headings":   chunk["headings"],   # stored as a JSON array
            "content":    chunk["content"],
            "chunk_text": chunk["chunk_text"],
        },
    )
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
]

result = client.upsert(
    collection_name=COLLECTION_NAME,
    points=points,
    wait=True,
)
print(f"Indexed {len(points)} points — status: {result.status}")

info = client.get_collection(COLLECTION_NAME)
print(f"Points     : {info.points_count}")
print(f"Dimensions : {info.config.params.vectors.size}")

# Retrieve the top-k most similar chunks for a given query.
def retrieve(
    query: str,
    top_k: int = 5
) -> list[dict]:
    """
    Embed the query and return the top-k most similar chunks.

    Args:
        query          : User's question.
        top_k          : Number of chunks to return.
        section_filter : Optional H2 heading to restrict the search scope.
    """
    query_vector = embedder.encode(query).tolist()

    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    return [{**hit.payload, "score": round(hit.score, 4)} for hit in hits.points]


results = retrieve("What is the leave policy?", top_k=3)
for r in results:
    print(f"[{r['score']}]  {r['headings']}")
    print(f"  {r['content'][:200]}…\n")


SYSTEM_PROMPT = """You are a helpful HR assistant.
Answer the user's question using ONLY the context provided below.
If the context does not contain enough information, say so — do not make things up.
Always cite the section name when referencing specific information."""

def build_context(retrieved_chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        parts.append(f"[Source {i}]\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        f"GROQ_API_KEY not found. Add it to {ENV_PATH} or export it in your shell."
    )

groq_client = Groq(api_key=api_key)
GROQ_MODEL  = "openai/gpt-oss-safeguard-20b"

def rag(query: str, top_k: int = 5):
    """
    End-to-end RAG pipeline:
      1. Retrieve relevant chunks from Qdrant
      2. Format them as a context block
      3. Send context + query to Groq and return the answer
    """
    # Step 1 — Retrieve
    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        return "No relevant content found in the document."

    # Step 2 — Build context
    context = build_context(chunks)

    # Step 3 — Generate
    user_message = f"Context:\n{context}\n\nQuestion: {query}"

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,   # Low = factual;  High = creative
    )
    return response.choices[0].message.content, context

answer, context = rag("How many casual leaves am I entitled to?")
print(answer)
print(f"{250*'='}")
print(f"\n\nSOURCES:\n {context}")