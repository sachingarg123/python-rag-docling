# Component 5 App Interface

This folder contains the application interface stack:


RAGAS (Component 4) remains independent and is run separately from:

- `02_rag_advanced/studies/ragas_ablation_study.py`
- `run_ragas_quick.sh`

## Backend

Start backend from repo root:

```bash
uv run uvicorn app_interface.backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend endpoints:

- `GET /health`
- `GET /users`
- `POST /auth/login`
- `POST /chat`

Demo users:

- `employee_user / pass123`
- `finance_user / pass123`
- `engineering_user / pass123`
- `marketing_user / pass123`
- `ceo_user / pass123`

## Frontend

Start frontend:

```bash
cd app_interface/frontend
npm install
npm run dev
```

Optional API base URL:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## What UI shows

- Login for 5 roles
- Chat answer
- Selected semantic route
- Active role and routed collections used
- Guardrail triggers/warnings
- Source document citations and page numbers

## Architecture

Frontend (Next.js) -> Backend API (FastAPI) ->
Component 3 Guardrails -> Component 2 Router + RBAC -> Component 1 Retrieval (Qdrant)
