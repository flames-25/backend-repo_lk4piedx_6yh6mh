"""
Database Schemas for Trimkart

Each Pydantic model maps to a MongoDB collection (lowercased class name).
Use these schemas for input validation in API routes.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

RoleType = Literal["MD", "CEO", "COO", "MANAGER", "EMPLOYEE"]
TaskStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED"]

class Department(BaseModel):
    name: str = Field(..., description="Department name")
    description: Optional[str] = Field(None, description="Department description")
    manager_user_id: Optional[str] = Field(None, description="Manager user id (stringified ObjectId)")

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    role: RoleType = Field("EMPLOYEE", description="User role in hierarchy")
    department_id: Optional[str] = Field(None, description="Department id (stringified ObjectId)")
    # password is handled separately; we store hashes in DB, not via schema

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: RoleType = "EMPLOYEE"
    department_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TaskUpdateEntry(BaseModel):
    user_id: str
    note: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    created_at: Optional[datetime] = None

class Task(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: str = Field(..., description="User id (stringified ObjectId)")
    assigned_by: str = Field(..., description="User id (stringified ObjectId)")
    department_id: Optional[str] = None
    status: TaskStatus = "PENDING"
    due_date: Optional[datetime] = None
    progress: int = Field(0, ge=0, le=100)
    updates: List[TaskUpdateEntry] = []
