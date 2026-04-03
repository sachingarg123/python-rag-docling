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
from datasets import Dataset
from ragas import evaluate
from langchain_groq import ChatGroq
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

from ragas.metrics.collections import (
    AnswerCorrectness,
    AnswerRelevancy,
    Faithfulness,
    ContextPrecision,
    ContextRecall,
)

from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    faithfulness,
    context_precision,
    context_recall,
)

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

def generate_answer(question: str, context: str) -> str:
    """Generate an answer based on context."""
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

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
    answer = generate_answer(query, context)
    return answer,context

answer, context = rag("How many casual leaves am I entitled to?")
print(answer)
print(f"{250*'='}")
print(f"\n\nSOURCES:\n {context}")



# sample questions
questions = [
    "What types of leaves are available to employees?",
    "How many casual leaves are employees entitled to per year?",
    "What is the maternity leave policy at AtliQ?",
    "What is the paternity leave entitlement?",
    "How much paid leave do employees get for medical emergencies?",
    "What is the process for applying for leave?",
    "What happens if an employee exceeds their casual leave limit?",
    "Are there any restrictions on when leaves can be taken?",
    "What is the notice period required for leave applications?",
    "What is the work-from-home policy at AtliQ?",
]

# Expected responses
ground_truths = [
    "AtliQ offers multiple types of leaves including casual leave, sick leave, maternity leave, paternity leave, bereavement leave, and medical emergency leave.",
    "Employees are entitled to 12 casual leaves per calendar year, which do not carry forward to the next year.",
    "Eligible female employees are entitled to 6 months (180 days) of paid maternity leave, with an option to extend unpaid leave.",
    "Male employees are entitled to 15 days of paid paternity leave within 6 months of the child's birth.",
    "Employees can take up to 5 days of paid leave for medical emergencies with proper documentation from a registered medical practitioner.",
    "Employees must submit leave applications through the HR portal at least 5 business days in advance, or immediately in case of emergencies.",
    "Casual leaves exceeding the annual limit require prior approval from the department manager and may result in leave without pay or salary deduction.",
    "Leaves cannot be taken during critical project deadlines or company events without manager approval. Annual leaves should be planned in advance.",
    "Standard notice period is 5 business days for planned leaves and immediate notification for emergency leaves with post-approval.",
    "AtliQ allows eligible employees to work from home up to 3 days per week with manager approval. Remote work requires prior arrangement and stable internet connectivity.",
]

rows = []

for question, ground_truth in zip(questions, ground_truths):
    print(f"Processing: {question}")

    # Retrieve relevant chunks
    retrieved_chunks = retrieve(question, top_k=5)
    contexts = [chunk["content"] for chunk in retrieved_chunks]

    # Generate answer
    answer = generate_answer(question, "\n\n---\n\n".join(contexts))

    # Store in format required by RAGAS
    rows.append({
        "question": question,
        "contexts": contexts,
        "answer": answer,
        "ground_truth": ground_truth,
    })

    evaluation_dataset = Dataset.from_list(rows)

print(f"\nEvaluation dataset created with {len(evaluation_dataset)} samples")
print("\nSample:")
print(evaluation_dataset[0])


ragas_llm = LangchainLLMWrapper(
    ChatGroq(
        model="llama-3.3-70b-versatile",   # any model at console.groq.com/docs
        temperature=0,
        api_key=os.environ.get("GROQ_API_KEY"),
    )
)

ragas_emb = LangchainEmbeddingsWrapper(
    HuggingFaceBgeEmbeddings(model_name="Qwen/Qwen3-Embedding-0.6B")
)

answer_correctness.llm = ragas_llm
answer_correctness.embeddings = ragas_emb

answer_relevancy.llm = ragas_llm
answer_relevancy.embeddings = ragas_emb

faithfulness.llm = ragas_llm
faithfulness.embeddings = ragas_emb

context_precision.llm = ragas_llm
context_precision.embeddings = ragas_emb

context_recall.llm = ragas_llm
context_recall.embeddings = ragas_emb

scores = evaluate(
    evaluation_dataset,
    metrics=[
        answer_correctness,
        answer_relevancy,
        faithfulness,
        context_precision,
        context_recall,
    ],
    llm=ragas_llm,
    embeddings=ragas_emb,
)