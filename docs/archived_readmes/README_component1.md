# FinBot Assignment - Component 1

This README is specific to Assignment Component 1:

- Document ingestion with Docling
- Hierarchical chunking with parent-child context
- RBAC enforcement at retrieval time in Qdrant

The original project README is intentionally left unchanged.

## 1. Goal

Build the first production-grade layer of FinBot so retrieval is both:

1. Structurally aware (good chunk quality for tables/sections)
2. Access-controlled (users cannot retrieve unauthorized data)

## 2. What Was Implemented

Component 1 now lives in the packaged layout:

- `02_rag_advanced/services/document_access_index_service.py`
- `02_rag_advanced/pipelines/finbot_runtime_pipeline.py`

### Key capabilities

1. Parse documents with `docling`
2. Chunk using `HierarchicalChunker`
3. Store leaf chunks plus parent section summaries
4. Attach required metadata for each chunk
5. Index vectors in Qdrant
6. Enforce RBAC using Qdrant metadata filters before LLM use

## 3. Metadata Schema

Each indexed chunk includes:

- `source_document`
- `collection`
- `access_roles`
- `section_title`
- `page_number`
- `chunk_type` (`text`, `table`, `heading`, `code`)
- `parent_chunk_id`

Additional operational fields are also stored:

- `chunk_id`
- `chunk_level` (`parent_summary` or `leaf`)
- `content`
- `chunk_text`

## 4. RBAC Rules

Role-to-collection mapping:

- `employee` -> `general`
- `finance` -> `general`, `finance`
- `engineering` -> `general`, `engineering`
- `marketing` -> `general`, `marketing`
- `c_level` -> all collections

Retrieval applies Qdrant filter constraints for:

1. Allowed collections for the role
2. Role membership in `access_roles`

If routed collection targets are not permitted for the role, retrieval raises a `PermissionError` immediately.

## 5. Setup

## Prerequisites

- Python virtual environment ready (`uv sync` already done)
- Qdrant running on `localhost:6333`

Start Qdrant with Docker if needed:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

## 6. Run Component 1 Demo

From repository root:

There is no standalone Component 1 demo script anymore. Use the packaged implementation directly:

- `02_rag_advanced/services/document_access_index_service.py` for ingestion and retrieval
- `02_rag_advanced/pipelines/finbot_runtime_pipeline.py` for integrated runtime behavior

Demo flow:

1. Ingest sample document with hierarchical chunking
2. Run role-aware retrieval (`employee` on `general`)
3. Demonstrate blocked retrieval (`engineering` requesting `finance`)

## 7. Use Your Real Documents

Update the document discovery or ingestion inputs in:

- `02_rag_advanced/services/document_access_index_service.py`
- `02_rag_advanced/pipelines/finbot_runtime_pipeline.py`

Example template:

```python
SOURCES = [
    SourceDocument(
        path_or_url="/absolute/path/to/general_policy.pdf",
        collection="general",
        access_roles=["employee", "finance", "engineering", "marketing", "c_level"],
    ),
    SourceDocument(
        path_or_url="/absolute/path/to/finance_report.pdf",
        collection="finance",
        access_roles=["finance", "c_level"],
    ),
    SourceDocument(
        path_or_url="/absolute/path/to/engineering_onboarding.md",
        collection="engineering",
        access_roles=["engineering", "c_level"],
    ),
    SourceDocument(
        path_or_url="/absolute/path/to/marketing_campaign.pdf",
        collection="marketing",
        access_roles=["marketing", "c_level"],
    ),
]
```

Then rerun the ingestion flow through the current pipeline or backend runtime.

## 8. Validation Checklist for Component 1

- Docling parsing runs for all sources
- Hierarchical chunks are created
- Parent summary chunks are indexed
- Metadata fields exist on every chunk
- RBAC blocks unauthorized retrieval at query level

## 9. Next Step

After your real document ingestion is confirmed, proceed to Component 2:

- Semantic routing
- Route and role intersection behavior
- Access-denied messaging for unauthorized route requests

---

# Component 2: Query Routing with Semantic Router

This README documents Component 2 implementation.

## 1. Goal

Add semantic query routing so questions are directed to the right document collections based on intent. Then intersect route output with user role for access control.

## 2. What Was Implemented

Component 2 now lives in the packaged layout:

- `02_rag_advanced/services/semantic_routing_service.py`
- `02_rag_advanced/pipelines/finbot_runtime_pipeline.py`

## 3. Five Routes Implemented

- `finance_route`: 12 utterances about budgets, revenue, financial metrics
- `engineering_route`: 12 utterances about systems, architecture, incidents
- `marketing_route`: 12 utterances about campaigns, brand, market analysis
- `hr_general_route`: 12 utterances about policies, leave, benefits
- `cross_department_route`: 10 utterances about company-wide topics

Each route has **10+ representative utterances** as required.

## 4. Role-Route Intersection

Route output is intersected with user role:

```
Query → Semantic Router → Route Collections
                              ↓
                         User Role → Role Collections
                              ↓
                    Intersection (accessible collections)
```

Example:
- Query routes to `finance` collection
- User role is `engineering`
- No intersection → **Access Denied**
- Polite message: "Role 'engineering' cannot access collections ['finance']"

## 5. RBAC Enforcement

Same matrix as Component 1:

- `employee` → `general` only
- `finance` → `general`, `finance`
- `engineering` → `general`, `engineering`
- `marketing` → `general`, `marketing`
- `c_level` → all collections

## 6. Auditability Logging

Every route operation logs:
- Route name
- User role
- Is accessible (yes/no)
- Collections accessed

Example log:
```
Query routing | Route: finance_route | User: engineering | IsAccessible: False | Accessible: []
```

## 7. Run Component 2 Demo

From repo root:

There is no standalone Component 2 demo script anymore. Use the packaged implementation directly:

- `02_rag_advanced/services/semantic_routing_service.py` for route evaluation
- `02_rag_advanced/pipelines/finbot_runtime_pipeline.py` for routing inside the end-to-end pipeline

Demo tests 8 scenarios:
1. Finance user asking about finance ✅
2. Engineering user asking about finance ❌
3. Engineering user asking about engineering ✅
4. Employee asking about HR ✅
5. Marketing user asking about marketing ✅
6. Employee asking cross-department ✅
7. C-level user asking about finance ✅
8. Marketing user asking about engineering ❌
