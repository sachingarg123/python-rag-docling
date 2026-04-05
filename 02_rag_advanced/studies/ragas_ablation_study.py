"""
RAGAS Ablation Study: Evaluate pipeline impact with results table.

This script runs RAGAS evaluation on the full pipeline and generates:
1. Baseline scores (Full Pipeline)
2. Results table with all RAGAS metrics
3. Markdown report with findings
4. JSON export for tracking

Current Implementation:
- Full pipeline evaluation (baseline)
- Component impact documented
- Results tracked for future ablations

Note: Full ablation variants (without guardrails, routing, etc.) require
architectural modifications to decouple components. Current version provides
baseline for comparison as components are refactored.
"""

from __future__ import annotations

from pathlib import Path
import sys
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import pandas as pd
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from pipelines.finbot_runtime_pipeline import FinBotRuntimePipeline
from services.ragas_service import RagasEvaluator, default_eval_items


def run_ragas_baseline() -> None:
    """Run RAGAS evaluation on full pipeline and save results."""
    
    # Ensure API keys are loaded
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "01_rag" / ".env"
    output_dir = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=env_path)

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            f"GROQ_API_KEY not found. Expected in {env_path} or current environment."
        )

    print("=" * 80)
    print("RAGAS EVALUATION - Full Pipeline Baseline")
    print("=" * 80)
    print()

    # Load evaluation dataset once
    print("[Step 1/2] Building RAGAS evaluation dataset...")
    pipeline = FinBotRuntimePipeline(collection_name="finsolve_component123")
    print("  ├─ Ensuring index is built...")
    points = pipeline.ingest()
    print(f"  └─ Indexed points: {points}")

    print("\n  Building evaluation dataset...")
    evaluator = RagasEvaluator(pipeline)
    items = default_eval_items()
    
    # Allow quick mode for testing
    quick_n = int(os.getenv("RAGAS_QUICK_N", "0"))
    if quick_n > 0:
        items = items[:quick_n]
        print(f"  Quick mode: using first {len(items)} questions")
    else:
        print(f"  Using all {len(items)} questions")

    dataset = evaluator.build_dataset(items)
    print(f"  Final dataset size: {len(dataset)} samples")
    print()

    # Run full pipeline evaluation
    print("[Step 2/2] Running RAGAS metrics on full pipeline...")
    print()

    try:
        scores = evaluator.run(dataset)
        
        print("BASELINE SCORES (Full Pipeline):")
        print("-" * 80)
        for metric, value in scores.items():
            print(f"  {metric:25s}: {value:.4f}")
        print()

    except Exception as e:
        print(f"✗ ERROR during evaluation: {str(e)}")
        raise

    # Save results
    results_file = output_dir / "ragas_baseline_results.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "dataset_size": len(dataset),
                "num_eval_items": len(items),
                "variant": "full_pipeline",
                "description": "Full pipeline with all components (guardrails, routing, LLM answer generation)",
                "scores": {k: float(v) for k, v in scores.items()},
                "component_stack": [
                    "Input Guardrails (off-topic, PII detection, rate limiting)",
                    "Semantic Routing (collection selection)",
                    "Qdrant Retrieval (with RBAC enforcement)",
                    "Answer Generation (fallback + LLM)",
                    "Output Guardrails (grounding checks, cross-role validation)"
                ]
            },
            f,
            indent=2
        )
    print(f"✓ Baseline results saved: {results_file}")

    # Generate markdown report
    report_file = output_dir / "RAGAS_RESULTS.md"
    generate_markdown_report(scores, len(dataset), len(items), report_file)
    print(f"✓ Markdown report saved: {report_file}")

    print("\n" + "=" * 80)
    print("RAGAS EVALUATION COMPLETE")
    print("=" * 80)


def generate_markdown_report(
    scores: dict[str, float],
    dataset_size: int,
    num_items: int,
    output_file: Path
) -> None:
    """Generate a markdown report of the RAGAS evaluation results."""
    
    report = [
        "# RAGAS Evaluation Results",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Dataset Size:** {dataset_size} Q&A samples",
        f"- **Evaluation Items:** {num_items} questions across 4 roles:",
        "  - 9 General HR questions (Employee role)",
        "  - 10 Finance questions (Finance role)",
        "  - 10 Engineering questions (Engineering role)", 
        "  - 10 Marketing questions (Marketing role)",
        "",
        "## Pipeline Configuration",
        "",
        "**Full Stack Components:**",
        "1. **Input Guardrails:** Off-topic, PII detection, rate limiting",
        "2. **Semantic Routing:** Dynamic collection selection based on query intent",
        "3. **Qdrant Retrieval:** Context fetching with role-based access control (RBAC)",
        "4. **Answer Generation:** Fallback + LLM-based detailed answers with citations",
        "5. **Output Guardrails:** Grounding checks, cross-role validation",
        "",
        "## RAGAS Metrics",
        "",
        "| Metric | Score | Interpretation |",
        "|--------|-------|-----------------|",
    ]

    # Add metric rows
    metric_interpretations = {
        "faithfulness": "Response is faithful to retrieved context (0-1)",
        "answer_relevancy": "Answer directly addresses the question (0-1)",
        "context_precision": "Retrieved context is precise for answering the question (0-1)",
        "context_recall": "Retrieved context contains all necessary information (0-1)",
        "answer_correctness": "Answer is factually correct and complete (0-1)",
    }

    for metric, score in scores.items():
        interpretation = metric_interpretations.get(metric, "")
        report.append(f"| {metric:25s} | {score:.4f} | {interpretation} |")

    report.extend([
        "",
        "## Metric Descriptions",
        "",
        "### Faithfulness",
        "Measures whether the answer is grounded in the retrieved context.",
        "- High score: Answers stick to provided facts",
        "- Low score: Answers contain unsupported claims",
        "",
        "### Answer Relevancy",
        "Measures how well the answer addresses the user's question.",
        "- High score: Question is directly and completely answered",
        "- Low score: Answer is off-topic or incomplete",
        "",
        "### Context Precision",
        "Measures whether retrieved context is relevant to the question.",
        "- High score: Retrieved documents are highly relevant",
        "- Low score: Retrieved documents contain noise/irrelevance",
        "",
        "### Context Recall",
        "Measures whether all necessary information was retrieved.",
        "- High score: All relevant facts from knowledge base were found",
        "- Low score: Important context was missed",
        "",
        "### Answer Correctness",
        "Measures overall factual correctness and completeness.",
        "- High score: Answers are accurate and comprehensive",
        "- Low score: Answers contain errors or lacking detail",
        "",
        "## Key Findings",
        "",
        "### Component Impact (Architectural Components)",
        "",
        "| Component | Impact Areas |",
        "|-----------|--------------|",
        "| **Input Guardrails** | Prevents off-topic queries from consuming context |",
        "| **Semantic Routing** | Ensures topic-relevant collections are selected |",
        "| **RBAC Enforcement** | Restricts context to authorized role permissions |",
        "| **LLM Answer Generation** | Improves answer quality through intelligent synthesis |",
        "| **Output Guardrails** | Validates grounding and prevents hallucination |",
        "",
        "## Recommendations",
        "",
        "1. **Monitor Faithfulness:** Track that answers remain grounded in sources",
        "2. **Improve Recall:** Adjust retrieval top-k if critical context is missed",
        "3. **Refine Routing:** Review semantic router to eliminate off-topic matches",
        "4. **Validate RBAC:** Ensure role-based filtering doesn't over-restrict",
        "",
        "## Next Steps (Future Ablations)",
        "",
        "To isolate component impact, the following ablation studies are planned:",
        "- [ ] Evaluate without input guardrails (measure false positives)",
        "- [ ] Evaluate without semantic routing (measure precision loss)",
        "- [ ] Evaluate without RBAC (measure information leakage)",
        "- [ ] Evaluate with fallback-only answers (measure LLM contribution)",
        "- [ ] Evaluate without output guardrails (measure hallucination rate)",
        "",
        "---",
        f"*Report generated by RAGAS Evaluation Script*",
    ])

    with open(output_file, "w") as f:
        f.write("\n".join(report))


if __name__ == "__main__":
    run_ragas_baseline()
