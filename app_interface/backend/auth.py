# User storage with metadata
DEMO_USERS = {
    "employee_user": {"password": "pass123", "role": "employee", "status": "active", "last_active": "5 min ago"},
    "finance_user": {"password": "pass123", "role": "finance", "status": "active", "last_active": "10 min ago"},
    "engineering_user": {"password": "pass123", "role": "engineering", "status": "blocked", "last_active": "2 days ago"},
    "marketing_user": {"password": "pass123", "role": "marketing", "status": "active", "last_active": "1 hour ago"},
    "ceo_user": {"password": "pass123", "role": "c_level", "status": "active", "last_active": "2 min ago"},
}

# Document storage
DOCUMENTS = {
    "1": {"name": "employee_handbook.pdf", "collection": "general", "status": "indexed", "size": "2.3 MB", "uploaded_at": "2024-04-01"},
    "2": {"name": "finance_policies.pdf", "collection": "finance", "status": "indexed", "size": "1.8 MB", "uploaded_at": "2024-04-02"},
    "3": {"name": "engineering_guide.pdf", "collection": "engineering", "status": "pending", "size": "5.2 MB", "uploaded_at": "2 hours ago"},
}

VALID_ROLES = {"employee", "finance", "engineering", "marketing", "c_level"}


def authenticate(username: str, password: str) -> tuple[bool, str | None]:
    user = DEMO_USERS.get(username)
    if not user:
        return False, None
    if user["password"] != password:
        return False, None
    return True, user["role"]


def add_user(username: str, password: str, role: str) -> tuple[bool, str]:
    """Add a new user"""
    if username in DEMO_USERS:
        return False, "User already exists"
    if role not in VALID_ROLES:
        return False, f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"
    
    DEMO_USERS[username] = {
        "password": password,
        "role": role,
        "status": "active",
        "last_active": "just now"
    }
    return True, f"User {username} created successfully"


def update_user_password(username: str, new_password: str) -> tuple[bool, str]:
    """Update user password"""
    if username not in DEMO_USERS:
        return False, "User not found"
    
    DEMO_USERS[username]["password"] = new_password
    return True, f"Password for {username} updated successfully"


def toggle_user_status(username: str) -> tuple[bool, str]:
    """Block or unblock a user"""
    if username not in DEMO_USERS:
        return False, "User not found"
    
    current_status = DEMO_USERS[username]["status"]
    new_status = "active" if current_status == "blocked" else "blocked"
    DEMO_USERS[username]["status"] = new_status
    
    return True, f"User {username} is now {new_status}"


def delete_user(username: str) -> tuple[bool, str]:
    """Delete a user"""
    if username not in DEMO_USERS:
        return False, "User not found"
    
    del DEMO_USERS[username]
    return True, f"User {username} deleted"


def add_document(name: str, collection: str, size: str = "0 MB") -> tuple[bool, str, str]:
    """Add a new document"""
    import uuid
    from datetime import datetime
    
    doc_id = str(uuid.uuid4())[:8]
    DOCUMENTS[doc_id] = {
        "name": name,
        "collection": collection,
        "status": "pending",
        "size": size,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return True, doc_id, f"Document {name} uploaded successfully"


def delete_document(doc_id: str) -> tuple[bool, str]:
    """Delete a document"""
    if doc_id not in DOCUMENTS:
        return False, "Document not found"
    
    doc_name = DOCUMENTS[doc_id]["name"]
    del DOCUMENTS[doc_id]
    return True, f"Document {doc_name} deleted"
