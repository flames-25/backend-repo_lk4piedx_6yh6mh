import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import List, Optional, Dict, Any
from bson import ObjectId
from passlib.context import CryptContext

from database import db, create_document, get_documents
from schemas import UserRegister, UserLogin, User, Department, Task, TaskUpdateEntry

app = FastAPI(title="Trimkart API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helpers

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    user = db["user"].find_one({"email": email})
    return user


@app.get("/")
def root():
    return {"message": "Trimkart backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# Auth endpoints (HTTP Basic for demo; can be swapped for JWT later)
@app.post("/auth/register")
def register(payload: UserRegister):
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = pwd_context.hash(payload.password)
    doc = {
        "name": payload.name,
        "email": payload.email,
        "password_hash": hashed,
        "role": payload.role,
        "department_id": payload.department_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    inserted_id = db["user"].insert_one(doc).inserted_id
    return {"id": str(inserted_id), "message": "Registered successfully"}


@app.post("/auth/login")
def login(payload: UserLogin):
    user = get_user_by_email(payload.email)
    if not user or not pwd_context.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # For simplicity, return user info; in production return JWT
    user["id"] = str(user.pop("_id"))
    user.pop("password_hash", None)
    return {"message": "Login successful", "user": user}


# Departments
@app.post("/departments")
def create_department(dep: Department):
    data = dep.model_dump()
    inserted_id = db["department"].insert_one({
        **data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }).inserted_id
    return {"id": str(inserted_id)}


@app.get("/departments")
def list_departments():
    deps = list(db["department"].find().sort("name"))
    for d in deps:
        d["id"] = str(d.pop("_id"))
    return deps


# Users
@app.get("/users")
def list_users(role: Optional[str] = None, department_id: Optional[str] = None):
    query: Dict[str, Any] = {}
    if role:
        query["role"] = role
    if department_id:
        query["department_id"] = department_id
    users = list(db["user"].find(query))
    for u in users:
        u["id"] = str(u.pop("_id"))
        u.pop("password_hash", None)
    return users


# Tasks
@app.post("/tasks")
def create_task(task: Task):
    data = task.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    data["updated_at"] = datetime.now(timezone.utc)
    inserted_id = db["task"].insert_one(data).inserted_id
    return {"id": str(inserted_id)}


@app.get("/tasks")
def list_tasks(status: Optional[str] = None, assigned_to: Optional[str] = None, department_id: Optional[str] = None):
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if assigned_to:
        query["assigned_to"] = assigned_to
    if department_id:
        query["department_id"] = department_id
    tasks = list(db["task"].find(query).sort("created_at", -1))
    for t in tasks:
        t["id"] = str(t.pop("_id"))
    return tasks


@app.post("/tasks/{task_id}/update")
def add_task_update(task_id: str, update: TaskUpdateEntry):
    upd = update.model_dump()
    if not upd.get("created_at"):
        upd["created_at"] = datetime.now(timezone.utc)
    res = db["task"].update_one({"_id": oid(task_id)}, {"$push": {"updates": upd}, "$set": {"updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Update added"}


@app.post("/tasks/{task_id}/status")
def set_task_status(task_id: str, status: str):
    if status not in ["PENDING", "IN_PROGRESS", "COMPLETED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = db["task"].update_one({"_id": oid(task_id)}, {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Status updated"}


# Simple analytics endpoints
@app.get("/analytics/overview")
def analytics_overview():
    total_users = db["user"].count_documents({})
    total_tasks = db["task"].count_documents({})
    completed = db["task"].count_documents({"status": "COMPLETED"})
    in_progress = db["task"].count_documents({"status": "IN_PROGRESS"})
    pending = db["task"].count_documents({"status": "PENDING"})
    return {
        "users": total_users,
        "tasks": total_tasks,
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "completion_rate": (completed / total_tasks * 100) if total_tasks else 0.0
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
