"""
Component 3: Guardrails for FinBot pipeline.

Includes input guardrails:
- Off-topic detection
- Prompt-injection detection
- PII detection/scrubbing
- Session rate limiting

And output checks:
- Optional grounding heuristic
- Optional cross-role leakage heuristic
- Source citation enforcement
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from typing import Iterable

from groq import Groq
from semantic_router import Route
from semantic_router.encoders import HuggingFaceEncoder
from semantic_router.routers import SemanticRouter

from services.semantic_routing_service import ROLE_TO_COLLECTIONS


@dataclass(frozen=True)
class GuardrailInputResult:
    allowed: bool
    sanitized_query: str
    triggered: list[str] = field(default_factory=list)
    message: str = ""


@dataclass(frozen=True)
class GuardrailOutputResult:
    flagged: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm_checked: bool = False


def _build_input_guardrail_router() -> SemanticRouter:
    off_topic_route = Route(
        name="off_topic",
        utterances=[
            "Tell me a joke",
            "Write me a poem",
            "What is the cricket score",
            "How do I bake a cake",
            "Who won the football match",
            "Recommend a movie",
            "Teach me guitar",
            "Tell me celebrity news",
            "How to lose weight quickly",
            "What is the weather today",
        ],
    )

    encoder = HuggingFaceEncoder(name="Qwen/Qwen3-Embedding-0.6B")
    return SemanticRouter(
        encoder=encoder,
        routes=[off_topic_route],
        auto_sync="local",
    )


class GuardrailsService:
    def __init__(
        self,
        max_queries_per_session: int = 20,
        grounding_model: str = "openai/gpt-oss-20b",
    ) -> None:
        self.max_queries_per_session = max_queries_per_session
        self.query_counts: dict[str, int] = {}
        self.input_router = _build_input_guardrail_router()
        self.grounding_model = grounding_model
        api_key = os.getenv("GROQ_API_KEY")
        self.grounding_client = Groq(api_key=api_key) if api_key else None

        # Fast regex checks to complement semantic route matching.
        self.injection_patterns = [
            re.compile(r"ignore\s+(all\s+)?(previous|above|system)?\s*instructions", re.I),
            re.compile(r"bypass\s+rbac", re.I),
            re.compile(r"act\s+as\s+.*(admin|unrestricted)", re.I),
            re.compile(r"show\s+all\s+documents", re.I),
            re.compile(r"reveal\s+(hidden|internal)\s+(prompt|message)", re.I),
        ]

        self.email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
        self.aadhaar_pattern = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
        self.bank_pattern = re.compile(r"\b\d{9,18}\b")
        self.domain_keywords = [
            "policy",
            "leave",
            "benefit",
            "finance",
            "revenue",
            "budget",
            "engineering",
            "api",
            "incident",
            "marketing",
            "campaign",
            "company",
            "employee",
            "onboard",
            "report",
            "roi",
            "sla",
        ]

    def _check_citation_mismatch(self, answer: str, contexts: Iterable[dict]) -> tuple[bool, list[str]]:
        """
        Check if answer cites page numbers that don't exist in retrieved context.
        Returns (has_mismatch, mismatched_pages).
        Looks specifically for explicit page citations like "page: 4", "page 5", "(page: Y)".
        """
        contexts_list = list(contexts)
        valid_pages = set()
        sources = {}
        
        for c in contexts_list:
            src = c.get("source_document", "unknown")
            page = c.get("page_number")
            if page is not None:
                valid_pages.add(page)
                sources[page] = src
        
        if not valid_pages:
            return False, []  # No page numbers in context, can't validate
        
        # Extract EXPLICIT page references from answer:
        # Matches: "page: 4", "page 4", "page=4", "(page 4)", "[page: 4]" 
        # But NOT "20 days" or other numbers not in page citation context
        page_citation_pattern = r'\b(?:page|p\.)\s*[:=]?\s*([0-9]+)\b'
        page_refs = re.findall(page_citation_pattern, answer, re.IGNORECASE)
        
        mismatched = []
        for page_str in page_refs:
            try:
                page_num = int(page_str)
                # Consider pages adjacent to valid pages as acceptable (scanning artifacts)
                if page_num not in valid_pages and not any(
                    abs(page_num - vp) <= 1 for vp in valid_pages
                ):
                    mismatched.append(page_num)
            except ValueError:
                pass
        
        return bool(mismatched), list(set(mismatched))

    def _llm_grounding_check(self, answer: str, contexts: Iterable[dict]) -> tuple[bool, list[str]]:
        """
        Returns (potentially_ungrounded, unsupported_claims).
        Falls back gracefully when no LLM client is available.
        """
        if not self.grounding_client:
            return False, []

        contexts_list = list(contexts)
        context_block = "\n\n".join(
            [
                (
                    f"[source={c.get('source_document')} page={c.get('page_number')}]\n"
                    f"{c.get('content', '')}"
                )
                for c in contexts_list
            ]
        )

        prompt = (
            "You are a strict grounding verifier for enterprise RAG. "
            "Given an answer and retrieved context, determine whether the answer contains "
            "financial figures, dates, policies, or specific claims that are not traceable to the context.\n\n"
            "Return ONLY valid JSON in this exact schema:\n"
            '{"potentially_ungrounded": bool, "unsupported_claims": ["..."]}\n\n'
            "Rules:\n"
            "- If every claim is directly supported by context, set potentially_ungrounded=false and unsupported_claims=[].\n"
            "- If any specific figures, dates, policies, or named claims lack explicit support, set potentially_ungrounded=true.\n"
            "- Be STRICT: if a page reference appears but content is vague, mark as ungrounded.\n"
            "- List specific unsupported claims, not generic categories.\n\n"
            f"ANSWER:\n{answer}\n\n"
            f"CONTEXT:\n{context_block}"
        )

        try:
            resp = self.grounding_client.chat.completions.create(
                model=self.grounding_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You output strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()

            # Some models may wrap JSON in markdown fences.
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

            data = json.loads(text)
            potentially_ungrounded = bool(data.get("potentially_ungrounded", False))
            unsupported_claims = data.get("unsupported_claims", []) or []
            if not isinstance(unsupported_claims, list):
                unsupported_claims = [str(unsupported_claims)]

            return potentially_ungrounded, [str(x) for x in unsupported_claims]
        except Exception:
            return False, []

    def _increment_session_count(self, session_id: str) -> int:
        self.query_counts[session_id] = self.query_counts.get(session_id, 0) + 1
        return self.query_counts[session_id]

    def check_input(
        self,
        query: str,
        user_role: str,
        session_id: str,
        scrub_pii: bool = True,
    ) -> GuardrailInputResult:
        triggered: list[str] = []
        sanitized_query = query

        if user_role not in ROLE_TO_COLLECTIONS:
            return GuardrailInputResult(
                allowed=False,
                sanitized_query=query,
                triggered=["unknown_role"],
                message=f"Unknown role: {user_role}",
            )

        count = self._increment_session_count(session_id)
        if count > self.max_queries_per_session:
            return GuardrailInputResult(
                allowed=False,
                sanitized_query=query,
                triggered=["rate_limit"],
                message=(
                    f"Rate limit reached for this session ({count} queries). "
                    f"Maximum allowed is {self.max_queries_per_session}."
                ),
            )

        lower_query = query.lower()
        has_domain_signal = any(keyword in lower_query for keyword in self.domain_keywords)

        for pattern in self.injection_patterns:
            if pattern.search(query):
                return GuardrailInputResult(
                    allowed=False,
                    sanitized_query=query,
                    triggered=["prompt_injection"],
                    message="Your request was blocked due to prompt injection risk.",
                )

        semantic_result = self.input_router(query)
        if semantic_result and semantic_result.name == "off_topic" and not has_domain_signal:
            return GuardrailInputResult(
                allowed=False,
                sanitized_query=query,
                triggered=["off_topic"],
                message=(
                    "Your query appears off-topic for FinBot. "
                    "Please ask about company policies, finance, engineering, or marketing documents."
                ),
            )

        pii_found = False
        if self.email_pattern.search(sanitized_query):
            pii_found = True
            if scrub_pii:
                sanitized_query = self.email_pattern.sub("[EMAIL_REDACTED]", sanitized_query)

        if self.aadhaar_pattern.search(sanitized_query):
            pii_found = True
            if scrub_pii:
                sanitized_query = self.aadhaar_pattern.sub("[AADHAAR_REDACTED]", sanitized_query)

        if self.bank_pattern.search(sanitized_query):
            pii_found = True
            if scrub_pii:
                sanitized_query = self.bank_pattern.sub("[BANK_ACCOUNT_REDACTED]", sanitized_query)

        if pii_found:
            triggered.append("pii_scrubbed" if scrub_pii else "pii_detected")

        return GuardrailInputResult(
            allowed=True,
            sanitized_query=sanitized_query,
            triggered=triggered,
            message="Input passed guardrails.",
        )

    def check_output(
        self,
        answer: str,
        contexts: Iterable[dict],
        user_role: str,
    ) -> GuardrailOutputResult:
        flagged: list[str] = []
        warnings: list[str] = []
        llm_checked = False
        contexts_list = list(contexts)

        # Check 1: Citation mismatch (page numbers inconsistent with context)
        has_citation_mismatch, mismatched_pages = self._check_citation_mismatch(answer, contexts_list)
        if has_citation_mismatch:
            flagged.append("citation_mismatch")
            warnings.append(
                f"Answer cites page numbers not found in retrieved context: {mismatched_pages}. "
                "This may indicate hallucinated sources."
            )

        # Check 2: Numeric claims without numeric support
        # Remove citations (e.g., "(source: X, page: 1)") before checking for ungrounded figures
        answer_without_citations = re.sub(r'\(source:[^)]*\)', '', answer)
        context_text = "\n".join(c.get("content", "") for c in contexts_list)
        
        answer_has_numbers = bool(re.search(r"\b\d+(?:\.\d+)?\b", answer_without_citations))
        context_has_numbers = bool(re.search(r"\b\d+(?:\.\d+)?\b", context_text))
        if answer_has_numbers and not context_has_numbers:
            flagged.append("potentially_ungrounded")
            warnings.append(
                "Response may contain ungrounded figures not present in retrieved context."
            )

        # Check 3: LLM grounding verification
        # Skip LLM check for aspirational statements (vision, mission, values)
        is_policy_statement = any(
            keyword in answer.lower() 
            for keyword in ["vision", "mission", "values", "principles", "culture", "commitment", "dedicated"]
        )
        
        llm_ungrounded = False
        unsupported_claims = []
        
        if not is_policy_statement:  # Only run strict LLM check for factual claims
            llm_ungrounded, unsupported_claims = self._llm_grounding_check(answer, contexts_list)
        
        if self.grounding_client:
            llm_checked = True
        if llm_ungrounded:
            flagged.append("potentially_ungrounded")
            warning = "Potentially ungrounded response detected by LLM grounding check."
            if unsupported_claims:
                warning += " Unsupported claims: " + "; ".join(unsupported_claims[:3])
            warnings.append(warning)

        # Check 4: Cross-role leakage detection
        allowed_collections = set(ROLE_TO_COLLECTIONS[user_role])
        forbidden_collection_terms = {
            "finance": ["budget", "revenue", "investor", "quarterly report"],
            "engineering": ["api", "incident", "runbook", "architecture"],
            "marketing": ["campaign", "brand guideline", "market share", "roi"],
        }

        lower_answer = answer.lower()
        for collection, terms in forbidden_collection_terms.items():
            if collection in allowed_collections:
                continue
            if any(t in lower_answer for t in terms):
                flagged.append("cross_role_leakage_risk")
                warnings.append(
                    f"Response may include terms from restricted collection '{collection}'."
                )
                break

        # Check 5: Citation presence and validity
        has_valid_citation = any(
            (c.get("source_document") and c.get("page_number") is not None)
            for c in contexts_list
        )
        if not has_valid_citation:
            flagged.append("missing_citation")
            warnings.append("No source citation with page number found in retrieved chunks.")

        return GuardrailOutputResult(flagged=flagged, warnings=warnings, llm_checked=llm_checked)
