from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from datasets import Dataset
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer

from pipelines.finbot_runtime_pipeline import FinBotRuntimePipeline


class SimpleSentenceEmbeddings:
    """Minimal LangChain-like embeddings adapter backed by sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()


@dataclass(frozen=True)
class EvalItem:
    question: str
    user_role: str
    ground_truth: str


def default_eval_items() -> list[EvalItem]:
    items: list[EvalItem] = []

    general_q = [
        "What is the leave policy?",
        "How many casual leaves are available?",
        "How do employees apply for leave?",
        "What are medical leave provisions?",
        "What is the work-from-home policy?",
        "What are employee benefits?",
        "What are company culture guidelines?",
        "Are there restrictions around leave approvals?",
        "How does maternity leave work?",
        "How does paternity leave work?",
    ]
    finance_q = [
        "What does the quarterly financial report say?",
        "What is the budget allocation summary for 2024?",
        "What are key financial highlights this period?",
        "What is the spending trend by department?",
        "What are vendor payment insights?",
        "What are notable revenue-related updates?",
        "What does the financial summary report mention?",
        "What are finance risk indicators?",
        "What does the budget variance narrative describe?",
        "What are executive finance takeaways?",
    ]
    engineering_q = [
        "What does the system SLA report describe?",
        "What are key points in engineering onboarding?",
        "What incidents are captured in incident logs?",
        "What does sprint metrics 2024 highlight?",
        "What does engineering master doc say about architecture?",
        "What reliability metrics are documented?",
        "What engineering process guidance is available?",
        "What are deployment or operational practices?",
        "What technical references are included in engineering docs?",
        "What are engineering priorities mentioned in docs?",
    ]
    marketing_q = [
        "What does campaign performance data say about ROI?",
        "What are key points from marketing report Q1 2024?",
        "What does marketing report 2024 summarize?",
        "What is discussed in customer acquisition report?",
        "What does marketing report Q2 2024 mention?",
        "What does marketing report Q3 2024 mention?",
        "What does marketing report Q4 2024 mention?",
        "What marketing insights are reported on campaign outcomes?",
        "What market-facing strategy signals appear in marketing docs?",
        "What does marketing data indicate about performance trends?",
    ]

    for q in general_q:
        items.append(EvalItem(q, "employee", "General HR/policy answer grounded in the handbook or HR data."))
    for q in finance_q:
        items.append(EvalItem(q, "finance", "Finance answer grounded in financial reports and budget docs."))
    for q in engineering_q:
        items.append(EvalItem(q, "engineering", "Engineering answer grounded in technical markdown documents."))
    for q in marketing_q:
        items.append(EvalItem(q, "marketing", "Marketing answer grounded in campaign and report documents."))

    return items


class RagasEvaluator:
    def __init__(self, pipeline: FinBotRuntimePipeline) -> None:
        self.pipeline = pipeline

    def build_dataset(self, items: list[EvalItem]) -> Dataset:
        rows: list[dict[str, Any]] = []

        for idx, item in enumerate(items, 1):
            result = self.pipeline.ask_for_eval(
                query=item.question,
                user_role=item.user_role,
                ground_truth=item.ground_truth,
                session_id=f"eval-session-{idx}",
                use_llm_answer=False,
            )
            if result.blocked:
                continue

            rows.append(
                {
                    "question": result.question,
                    "contexts": result.contexts,
                    "answer": result.answer,
                    "ground_truth": result.ground_truth,
                }
            )

        if not rows:
            raise RuntimeError("No evaluable rows generated; all queries were blocked.")

        return Dataset.from_list(rows)

    def run(self, dataset: Dataset) -> dict[str, float]:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for RAGAS evaluation.")

        ragas_llm = LangchainLLMWrapper(
            ChatGroq(
                model="llama-3.1-8b-instant",
                temperature=0,
                api_key=api_key,
                max_retries=1,
                timeout=60,
            )
        )
        ragas_emb = LangchainEmbeddingsWrapper(SimpleSentenceEmbeddings("all-MiniLM-L6-v2"))

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

        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
                answer_correctness,
            ],
            llm=ragas_llm,
            embeddings=ragas_emb,
        )

        df = result.to_pandas()
        return {
            "faithfulness": float(df["faithfulness"].mean()),
            "answer_relevancy": float(df["answer_relevancy"].mean()),
            "context_precision": float(df["context_precision"].mean()),
            "context_recall": float(df["context_recall"].mean()),
            "answer_correctness": float(df["answer_correctness"].mean()),
        }

    def run_ablation(self, items: list[EvalItem]) -> dict[str, dict[str, float]]:
        dataset = self.build_dataset(items)
        return {"full_pipeline": self.run(dataset)}

    def _slice_dataset(self, dataset: Dataset, start: int, end: int) -> Dataset:
        rows = [dataset[i] for i in range(start, min(end, len(dataset)))]
        return Dataset.from_list(rows)

    def run_in_batches(self, dataset: Dataset, batch_size: int = 10) -> dict[str, Any]:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")

        total = len(dataset)
        if total == 0:
            raise RuntimeError("Dataset is empty; cannot run RAGAS.")

        batch_scores: list[dict[str, float]] = []
        batch_ranges: list[tuple[int, int]] = []

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            ds_batch = self._slice_dataset(dataset, start, end)
            scores = self.run(ds_batch)
            batch_scores.append(scores)
            batch_ranges.append((start + 1, end))

        keys = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
            "answer_correctness",
        ]

        aggregate = {
            k: float(sum(s[k] for s in batch_scores) / len(batch_scores))
            for k in keys
        }

        return {
            "aggregate": aggregate,
            "batch_scores": batch_scores,
            "batch_ranges": batch_ranges,
            "total_rows": total,
            "batch_size": batch_size,
            "num_batches": len(batch_scores),
        }