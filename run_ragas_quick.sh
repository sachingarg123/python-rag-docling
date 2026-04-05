#!/bin/bash

# RAGAS Evaluation Quick Start Script
# This script runs RAGAS baseline evaluation with configurable test size

set -e

PROJECT_ROOT="/Users/sachinga@backbase.com/Documents/AI Learning/python-rag-docling/python-rag-docling"
cd "$PROJECT_ROOT"

echo "==============================================="
echo "FinBot RAGAS Evaluation - Quick Start"
echo "==============================================="
echo ""

# Configuration
MODE="${1:-full}"  # 'quick' for 5 questions, 'fast' for 10, 'full' for all 40

case "$MODE" in
    quick)
        echo "Mode: QUICK (5 questions - ~2-3 minutes)"
        export RAGAS_QUICK_N=5
        ;;
    fast)
        echo "Mode: FAST (10 questions - ~5-8 minutes)"
        export RAGAS_QUICK_N=10
        ;;
    full)
        echo "Mode: FULL (40 questions - ~15-25 minutes)"
        export RAGAS_QUICK_N=0
        ;;
    *)
        echo "Usage: $0 [quick|fast|full]"
        exit 1
        ;;
esac

echo ""
echo "Prerequisites check:"
echo "  ✓ Backend running on port 8000"
echo "  ✓ Qdrant running on port 6333"
echo "  ✓ GROQ_API_KEY set in .env"
echo ""

# Activate environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Run evaluation
echo ""
echo "Starting RAGAS evaluation..."
echo "==============================================="
echo ""

uv run 02_rag_advanced/studies/ragas_ablation_study.py

echo ""
echo "==============================================="
echo "Evaluation complete!"
echo "Results saved to:"
echo "  • 02_rag_advanced/ragas_baseline_results.json"
echo "  • 02_rag_advanced/RAGAS_RESULTS.md"
echo "==============================================="
