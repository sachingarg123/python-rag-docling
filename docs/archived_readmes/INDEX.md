# Archived Documentation Index

This folder contains detailed component-specific documentation that has been archived from the main project root. Please refer to the main [README.md](../../README.md) for the comprehensive project overview.

---

## 📚 Documentation Files

### 1. **README_RETRIEVAL_IMPROVEMENTS.md**
- **Topic:** Component 1-2 (RAG Backend Improvements)
- **Content:**
  - 7-layer guardrail system architecture
  - False positive elimination (policy exemption, citation filtering)
  - Retrieval improvements breakdown
  - Performance metrics
- **When to Use:** Understanding guardrail validation or RAG improvements

### 2. **README_AUTHENTICATION_SECURITY.md**
- **Topic:** Component 5 (Authentication & Security)
- **Content:**
  - User authentication flow
  - Role-based access control (RBAC) implementation
  - Session management
  - Security best practices
- **When to Use:** Implementing authentication features or understanding security model

### 3. **README_UI_REDESIGN.md**
- **Topic:** Component 5 (UI/UX Redesign)
- **Content:**
  - Dark mode color scheme
  - Typography and spacing standards
  - Component design patterns
  - Chat interface details
  - Admin dashboard layout
- **When to Use:** Frontend development or UI component consistency

### 4. **README_component1.md**
- **Topic:** Component 1 (Basic RAG Implementation)
- **Content:**
  - Initial RAG pipeline setup
  - Document parsing workflow
  - Chunking strategy
  - Embedding and retrieval basics
- **When to Use:** Understanding RAG fundamentals or legacy setup

### 5. **README.md** (App Interface)
- **Topic:** Component 5 (Application Interface)
- **Content:**
  - FastAPI backend structure
  - Next.js frontend setup
  - Running instructions
  - API endpoint overview
- **When to Use:** Setting up the application or API integration

---

## 🔗 Quick Navigation

| Need | Read |
|------|------|
| Understand guardrails | README_RETRIEVAL_IMPROVEMENTS.md |
| Setup authentication | README_AUTHENTICATION_SECURITY.md |
| Modify UI/styling | README_UI_REDESIGN.md |
| Learn RAG basics | README_component1.md |
| Setup application | README.md (in this folder) or main README.md |

---

## 📝 Reference from Main README

For comprehensive guidance, refer to the main [README.md](../../README.md) which includes:
- ✅ Complete tech stack overview
- ✅ Full architecture diagrams
- ✅ RBAC enforcement flow
- ✅ All features documentation
- ✅ Getting started guide
- ✅ API documentation
- ✅ Troubleshooting guide
- ✅ Future enhancements

---

## 💡 Legacy Documentation Notes

These archived files contain detailed deep-dives into specific components that were created during development phases. They are preserved for:
- Historical reference
- Detailed technical specifications
- Component-specific implementation details
- Design decision rationale

Current code organization differs from some historical descriptions in these documents. The active implementation now uses package-based segregation inside `02_rag_advanced/services`, `02_rag_advanced/pipelines`, and `02_rag_advanced/studies`, and the old standalone `run_component*.py` helpers have been removed.

For new contributors, start with the main **README.md** first, then refer to these files as needed.

---

**Last Updated:** April 5, 2026  
**Archive Created:** April 5, 2026
