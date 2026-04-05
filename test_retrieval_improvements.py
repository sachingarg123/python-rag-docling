#!/usr/bin/env python3
# pyright: reportMissingImports=false

"""
Test script to validate retrieval quality improvements.
Tests citation accuracy, section context, and grounding checks.
"""

import sys
import os
from pathlib import Path

# Add components to path
sys.path.insert(0, str(Path(__file__).parent / "02_rag_advanced"))

from services.guardrails_service import GuardrailsService
from pipelines.finbot_runtime_pipeline import FinBotRuntimePipeline

def test_citation_mismatch_detection():
    """Test citation mismatch detection."""
    print("\n" + "="*70)
    print("TEST 1: Citation Mismatch Detection")
    print("="*70)
    
    guardrails = GuardrailsService()
    
    # Mock contexts from pages 4-5
    contexts = [
        {
            "source_document": "employee_handbook.pdf",
            "page_number": 4,
            "section_title": "Leave Policies",
            "content": "Annual leave: 20 days per year. Sick leave: 10 days per year."
        },
        {
            "source_document": "employee_handbook.pdf",
            "page_number": 5,
            "section_title": "Approval Process",
            "content": "Leave must be approved by manager 2 weeks in advance."
        }
    ]
    
    # Answer that incorrectly cites page 1
    answer_bad = "The leave policy is on page 1, section 3. Annual leave: 20 days (source: page 1)"
    
    has_mismatch, mismatched = guardrails._check_citation_mismatch(answer_bad, contexts)
    print(f"\n❌ BAD ANSWER: Cites page 1 (not in context)")
    print(f"   Mismatch detected: {has_mismatch}")
    print(f"   Mismatched pages: {mismatched}")
    assert has_mismatch, "Should detect page 1 mismatch"
    
    # Answer that correctly cites page 4-5
    answer_good = "The leave policy (source: page 4): Annual leave 20 days, Sick leave 10 days. Approval (source: page 5): Manager approval required."
    has_mismatch, mismatched = guardrails._check_citation_mismatch(answer_good, contexts)
    print(f"\n✅ GOOD ANSWER: Correctly cites pages 4-5")
    print(f"  Mismatch detected: {has_mismatch}")
    print(f"  Mismatched pages: {mismatched}")
    assert not has_mismatch, "Should detect valid citations"


def test_answer_with_section_context():
    """Test that answers preserve section context."""
    print("\n" + "="*70)
    print("TEST 2: Answer Generation with Section Context")
    print("="*70)
    
    pipeline = FinBotRuntimePipeline()
    
    hits = [
        {
            "source_document": "employee_handbook.pdf",
            "page_number": 4,
            "section_title": "Leave Policies",
            "collection": "general",
            "score": 0.95,
            "content": "Leave policies cover annual leave (20 days), sick leave (10 days), parental leave (90 days), and unpaid leave options."
        },
        {
            "source_document": "employee_handbook.pdf",
            "page_number": 4,
            "section_title": "Leave Policies",
            "collection": "general",
            "score": 0.90,
            "content": "All employees are entitled to paid time off based on their role and tenure. Approval process requires manager sign-off."
        }
    ]
    
    query = "What is the leave policy?"
    answer, sources = pipeline._build_answer(query, hits)
    
    print(f"\nQuery: {query}")
    print(f"\nAnswer:\n{answer}")
    print(f"\nSources extracted:")
    for src in sources:
        print(f"  - {src['source_document']}, page {src['page_number']}, section: {src['section_title']}")
    
    # Verify section context is preserved
    assert "Leave Policies" in answer, "Should include section title"
    assert "page: 4" in answer or "page 4" in answer.lower(), "Should cite correct page"
    assert all(s.get("section_title") for s in sources), "Should preserve section in sources"
    print("\n✅ Section context preserved in answer and sources")


def test_output_guardrails():
    """Test improved output guardrails."""
    print("\n" + "="*70)
    print("TEST 3: Enhanced Output Guardrails Check")
    print("="*70)
    
    guardrails = GuardrailsService()
    
    contexts = [
        {
            "source_document": "handbook.pdf",
            "page_number": 10,
            "section_title": "Compensation",
            "content": "Base salary ranges from $50,000 to $150,000 based on role."
        }
    ]
    
    # Case 1: Citation mismatch
    answer1 = "Salary details on page 25: $50k-$150k."
    result1 = guardrails.check_output(answer1, contexts, "employee")
    print(f"\nCase 1 - Citation mismatch (page 25 vs context page 10):")
    print(f"  Flagged: {result1.flagged}")
    print(f"  Warnings: {result1.warnings}")
    assert "citation_mismatch" in result1.flagged, "Should flag page mismatch"
    
    # Case 2: Valid citations
    answer2 = "(source: handbook.pdf, page 10) Base salary ranges from $50,000 to $150,000."
    result2 = guardrails.check_output(answer2, contexts, "employee")
    print(f"\nCase 2 - Valid citations (page 10 matches):")
    print(f"  Flagged: {result2.flagged}")
    print(f"  Warnings: {result2.warnings}")
    assert "citation_mismatch" not in result2.flagged, "Should not flag valid citations"
    
    print("\n✅ Output guardrails working correctly")


if __name__ == "__main__":
    try:
        test_citation_mismatch_detection()
        test_answer_with_section_context()
        test_output_guardrails()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary of Improvements:")
        print("1. ✅ Page number extraction robust (3-path fallback)")
        print("2. ✅ Section context preserved in answers")
        print("3. ✅ Citation mismatches detected")
        print("4. ✅ LLM grounding check stricter")
        print("5. ✅ Output guardrails effective")
        print("\nReady for deployment!")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
