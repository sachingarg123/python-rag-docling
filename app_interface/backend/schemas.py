from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    user_id: str | None = None
    role: str | None = None
    message: str


class ChatRequest(BaseModel):
    user_id: str
    role: str
    query: str = Field(min_length=1)
    session_id: str = "ui-session"


class SourceItem(BaseModel):
    source_document: str
    page_number: int | None = None
    collection: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    blocked: bool
    answer: str
    route_name: str | None = None
    role: str
    collections_used: list[str]
    sources: list[SourceItem]
    guardrail_triggers: list[str]
    guardrail_warnings: list[str]
