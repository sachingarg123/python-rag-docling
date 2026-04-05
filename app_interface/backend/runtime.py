"""Runtime integration for the application backend."""

# pyright: reportMissingImports=false

from __future__ import annotations

from pathlib import Path
import sys
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_DIR = REPO_ROOT / "02_rag_advanced"

# Load API keys and runtime config from existing env file.
load_dotenv(REPO_ROOT / "01_rag" / ".env")

# Make component modules importable from this backend package.
sys.path.insert(0, str(COMPONENTS_DIR))

from pipelines.finbot_runtime_pipeline import FinBotRuntimePipeline  # noqa: E402


class FinBotAppService:
    def __init__(self) -> None:
        self.pipeline = FinBotRuntimePipeline(collection_name="finsolve_component123")
        self._indexed = False

    def ensure_index(self) -> int:
        if not self._indexed:
            points = self.pipeline.ingest()
            self._indexed = True
            return points
        return 0

    def ask(self, query: str, user_role: str, session_id: str):
        return self.pipeline.ask(query=query, user_role=user_role, session_id=session_id)
