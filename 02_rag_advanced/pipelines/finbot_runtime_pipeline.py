"""
Combined pipeline: Component 1 + Component 2 + Component 3.

Flow:
1) Input guardrails
2) Semantic route selection
3) RBAC intersection
4) Retrieval from Qdrant with route+role filter
5) Simple grounded answer assembly
6) Output checks and warnings
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from groq import Groq

from services.document_access_index_service import DocumentAccessIndexService, SourceDocument
from services.semantic_routing_service import SemanticRoutingService
from services.guardrails_service import GuardrailsService


DATA_ROOT = Path("/Users/sachinga@backbase.com/Downloads/hTt9A56seib9ShZy/data")
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".docx", ".csv"}
COLLECTION_ACCESS = {
    "general": ["employee", "finance", "engineering", "marketing", "c_level"],
    "finance": ["finance", "c_level"],
    "engineering": ["engineering", "c_level"],
    "marketing": ["marketing", "c_level"],
}


@dataclass(frozen=True)
class FinBotResponse:
    blocked: bool
    answer: str
    route_name: str | None
    role: str
    collections_used: list[str]
    sources: list[dict]
    guardrail_triggers: list[str]
    guardrail_warnings: list[str]


@dataclass(frozen=True)
class FinBotEvalResponse:
    blocked: bool
    question: str
    user_role: str
    route_name: str | None
    contexts: list[str]
    answer: str
    ground_truth: str
    block_reason: str | None


def discover_sources(data_root: Path) -> list[SourceDocument]:
    sources: list[SourceDocument] = []
    folder_to_collection = {
        "general": "general",
        "hr": "general",
        "finance": "finance",
        "engineering": "engineering",
        "marketing": "marketing",
    }

    for folder_name, collection in folder_to_collection.items():
        folder_path = data_root / folder_name
        if not folder_path.exists():
            continue
        for file_path in folder_path.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            sources.append(
                SourceDocument(
                    path_or_url=str(file_path),
                    collection=collection,
                    access_roles=COLLECTION_ACCESS[collection],
                )
            )
    return sources


class FinBotRuntimePipeline:
    def __init__(self, collection_name: str = "finsolve_component123") -> None:
        self.indexer = DocumentAccessIndexService(collection_name=collection_name)
        self.router = SemanticRoutingService()
        self.guardrails = GuardrailsService(max_queries_per_session=20)
        api_key = os.getenv("GROQ_API_KEY")
        self.answer_llm = Groq(api_key=api_key) if api_key else None
        self.answer_model = "openai/gpt-oss-20b"

    def ingest(self, data_root: Path = DATA_ROOT) -> int:
        sources = discover_sources(data_root)
        if not sources:
            raise RuntimeError(
                f"No supported documents found under {data_root}. "
                "Expected extensions: .pdf, .md, .docx, .csv"
            )
        return self.indexer.ingest(sources)

    def _build_answer(self, query: str, hits: list[dict]) -> tuple[str, list[dict]]:
        """Build extractive answer from top hits, preserving section context."""
        if not hits:
            return "I could not find relevant information in the accessible documents.", []

        top = hits[:3]
        bullet_lines = []
        sources = []
        for i, h in enumerate(top, 1):
            src = h.get("source_document", "unknown")
            page = h.get("page_number")
            section = h.get("section_title", "document_root")
            content = (h.get("content", "") or "").strip().replace("\n", " ")
            snippet = content[:250] + ("..." if len(content) > 250 else "")
            
            # Include section hierarchy for context
            section_prefix = f"[{section}] " if section and section != "document_root" else ""
            bullet_lines.append(
                f"{i}. {section_prefix}{snippet}\n   (source: {src}, page: {page})"
            )
            sources.append(
                {
                    "source_document": src,
                    "page_number": page,
                    "section_title": section,
                    "collection": h.get("collection"),
                    "score": h.get("score"),
                }
            )

        answer = (
            f"Based on {len(top)} relevant document excerpt(s):\n"
            + "\n".join(bullet_lines)
        )
        return answer, sources

    def _generate_llm_answer(self, query: str, hits: list[dict]) -> str | None:
        """Generate detailed LLM answer with mandatory source citations."""
        if not self.answer_llm or not hits:
            return None

        context_lines = []
        for i, h in enumerate(hits[:6], 1):
            src = h.get("source_document", "unknown")
            page = h.get("page_number", "N/A")
            section = h.get("section_title", "document_root")
            content = h.get("content", "").strip()
            context_lines.append(
                f"[{i}] source={src}, page={page}, section={section}\n{content}"
            )
        context_block = "\n\n".join(context_lines)

        prompt = (
            "You are a detailed enterprise knowledge assistant. Your task:\n"
            "1. Answer the question comprehensively using ONLY the provided context\n"
            "2. Extract and state specific facts, numbers, dates, and policies from the context\n"
            "3. For EVERY key claim, include explicit citation in format: (source: X, page: Y)\n"
            "4. Do not invent or assume any information not in the context\n"
            "5. If context is incomplete, clearly state what is missing\n\n"
            "CRITICAL: Include [source: X, page: Y] after each factual statement.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {query}\n\n"
            "Detailed answer with mandatory source citations:"
        )

        try:
            resp = self.answer_llm.chat.completions.create(
                model=self.answer_model,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict, grounded enterprise assistant. "
                            "Always cite sources. Format: (source: document_name, page: X). "
                            "Never make unsupported claims."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return None

    def ask(self, query: str, user_role: str, session_id: str = "default") -> FinBotResponse:
        input_check = self.guardrails.check_input(
            query=query,
            user_role=user_role,
            session_id=session_id,
            scrub_pii=True,
        )
        if not input_check.allowed:
            return FinBotResponse(
                blocked=True,
                answer=input_check.message,
                route_name=None,
                role=user_role,
                collections_used=[],
                sources=[],
                guardrail_triggers=input_check.triggered,
                guardrail_warnings=[],
            )

        route_result = self.router.route(
            query=input_check.sanitized_query,
            user_role=user_role,
        )
        if not route_result.is_accessible:
            return FinBotResponse(
                blocked=True,
                answer=route_result.message,
                route_name=route_result.route_name,
                role=user_role,
                collections_used=[],
                sources=[],
                guardrail_triggers=input_check.triggered + ["rbac_block"],
                guardrail_warnings=[],
            )

        hits = self.indexer.retrieve(
            query=input_check.sanitized_query,
            user_role=user_role,
            top_k=10,  # Increased from 5 to 10
            route_collections=route_result.accessible_collections,
            min_similarity_score=0.5,  # Filter low-quality matches
            chunk_level="leaf",  # Prefer detailed chunks over parent summaries
        )

        fallback_answer, sources = self._build_answer(input_check.sanitized_query, hits)
        llm_answer = self._generate_llm_answer(input_check.sanitized_query, hits)
        answer = llm_answer if llm_answer else fallback_answer
        output_check = self.guardrails.check_output(
            answer=answer,
            contexts=hits,
            user_role=user_role,
        )

        if output_check.warnings:
            answer = answer + "\n\nWarnings:\n- " + "\n- ".join(output_check.warnings)

        if "potentially_ungrounded" in output_check.flagged:
            answer = (
                answer
                + "\n\nDisclaimer: This response may be partially ungrounded. "
                "Please verify key figures/dates against the cited source chunks."
            )

        return FinBotResponse(
            blocked=False,
            answer=answer,
            route_name=route_result.route_name,
            role=user_role,
            collections_used=route_result.accessible_collections,
            sources=sources,
            guardrail_triggers=input_check.triggered + output_check.flagged,
            guardrail_warnings=output_check.warnings,
        )

    def ask_for_eval(
        self,
        query: str,
        user_role: str,
        ground_truth: str,
        session_id: str = "eval",
        use_llm_answer: bool = False,
    ) -> FinBotEvalResponse:
        input_check = self.guardrails.check_input(
            query=query,
            user_role=user_role,
            session_id=session_id,
            scrub_pii=True,
        )
        if not input_check.allowed:
            return FinBotEvalResponse(
                blocked=True,
                question=query,
                user_role=user_role,
                route_name=None,
                contexts=[],
                answer=input_check.message,
                ground_truth=ground_truth,
                block_reason="input_guardrail",
            )

        route_result = self.router.route(
            query=input_check.sanitized_query,
            user_role=user_role,
        )
        if not route_result.is_accessible:
            return FinBotEvalResponse(
                blocked=True,
                question=query,
                user_role=user_role,
                route_name=route_result.route_name,
                contexts=[],
                answer=route_result.message,
                ground_truth=ground_truth,
                block_reason="rbac_block",
            )

        hits = self.indexer.retrieve(
            query=input_check.sanitized_query,
            user_role=user_role,
            top_k=5,
            route_collections=route_result.accessible_collections,
        )
        contexts = [h.get("content", "") for h in hits]

        fallback_answer, _ = self._build_answer(input_check.sanitized_query, hits)
        if use_llm_answer:
            llm_answer = self._generate_llm_answer(input_check.sanitized_query, hits)
            answer = llm_answer if llm_answer else fallback_answer
        else:
            answer = fallback_answer

        return FinBotEvalResponse(
            blocked=False,
            question=query,
            user_role=user_role,
            route_name=route_result.route_name,
            contexts=contexts,
            answer=answer,
            ground_truth=ground_truth,
            block_reason=None,
        )
