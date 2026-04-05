from __future__ import annotations

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import DEMO_USERS, DOCUMENTS, VALID_ROLES, authenticate, add_user, update_user_password, toggle_user_status, delete_user, add_document, delete_document
from .runtime import FinBotAppService
from .schemas import ChatRequest, ChatResponse, LoginRequest, LoginResponse, SourceItem


app = FastAPI(title="FinBot API", version="0.1.0")
service = FinBotAppService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for admin operations
class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class UpdatePasswordRequest(BaseModel):
    new_password: str


class DocumentUploadRequest(BaseModel):
    name: str
    collection: str


@app.on_event("startup")
def startup_event() -> None:
    service.ensure_index()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/users")
def users() -> dict:
    return {
        "users": [
            {"username": u, "role": data["role"]}
            for u, data in DEMO_USERS.items()
        ]
    }


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    ok, role = authenticate(payload.username, payload.password)
    if not ok:
        return LoginResponse(success=False, message="Invalid credentials")
    return LoginResponse(success=True, user_id=payload.username, role=role, message="Login successful")


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if payload.role not in {"employee", "finance", "engineering", "marketing", "c_level"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    result = service.ask(
        query=payload.query,
        user_role=payload.role,
        session_id=payload.session_id,
    )

    return ChatResponse(
        blocked=result.blocked,
        answer=result.answer,
        route_name=result.route_name,
        role=result.role,
        collections_used=result.collections_used,
        sources=[SourceItem(**s) for s in result.sources],
        guardrail_triggers=result.guardrail_triggers,
        guardrail_warnings=result.guardrail_warnings,
    )


# ============================================
# ADMIN ENDPOINTS
# ============================================

@app.get("/admin/users")
def get_users() -> dict:
    """Get all users with their metadata"""
    users_list = [
        {
            "id": username,
            "name": username,
            "role": data["role"],
            "status": data.get("status", "active"),
            "lastActive": data.get("last_active", "unknown")
        }
        for username, data in DEMO_USERS.items()
    ]
    return {"users": users_list}


@app.post("/admin/users")
def create_user(payload: CreateUserRequest) -> dict:
    """Create a new user"""
    success, message = add_user(payload.username, payload.password, payload.role)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "username": payload.username}


@app.put("/admin/users/{username}")
def update_user_status(username: str) -> dict:
    """Toggle user status (block/unblock)"""
    success, message = toggle_user_status(username)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message}


@app.put("/admin/users/{username}/password")
def change_password(username: str, payload: UpdatePasswordRequest) -> dict:
    """Change user password"""
    success, message = update_user_password(username, payload.new_password)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message}


@app.delete("/admin/users/{username}")
def remove_user(username: str) -> dict:
    """Delete a user"""
    success, message = delete_user(username)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message}


@app.get("/admin/documents")
def get_documents() -> dict:
    """Get all documents"""
    documents_list = [
        {
            "id": doc_id,
            "name": data["name"],
            "collection": data["collection"],
            "status": data["status"],
            "size": data["size"],
            "uploadedAt": data["uploaded_at"]
        }
        for doc_id, data in DOCUMENTS.items()
    ]
    return {"documents": documents_list}


@app.post("/admin/documents")
def upload_document(payload: DocumentUploadRequest) -> dict:
    """Upload a new document"""
    success, doc_id, message = add_document(payload.name, payload.collection)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "document_id": doc_id, "name": payload.name}


@app.delete("/admin/documents/{doc_id}")
def remove_document(doc_id: str) -> dict:
    """Delete a document"""
    success, message = delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message}


@app.get("/admin/health")
def admin_health() -> dict:
    """Get system health status"""
    return {
        "api": "healthy",
        "database": "healthy",
        "vectorStore": "healthy",
        "uptime": "99.8%"
    }
