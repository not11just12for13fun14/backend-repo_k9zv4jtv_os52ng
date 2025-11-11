"""
Database Schemas for A&V TechSolutions – Student Project Portal

Each Pydantic model represents a MongoDB collection. The collection name is the lowercase
of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal, List
from datetime import datetime

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    role: Literal["student", "admin"] = Field("student", description="User role")

class Project(BaseModel):
    studentId: str = Field(..., description="ID of the student user")
    title: str = Field(..., description="Project title")
    description: Optional[str] = Field(None, description="Project description")
    technology: Literal["Python", "Java", "AI/ML", "IoT", "Web", "Android"]
    status: Literal["Requested", "In Review", "In Development", "Completed"] = "Requested"
    paymentStatus: Literal["pending", "verified"] = "pending"
    paymentProofURL: Optional[str] = Field(None, description="URL to payment proof image")
    adminRemarks: Optional[str] = Field(None, description="Notes from admin")
    deliverables: Optional[List[str]] = Field(default_factory=list, description="List of file URLs (code/report/PPT)")

class Payment(BaseModel):
    studentId: str = Field(..., description="Student user id")
    projectId: Optional[str] = Field(None, description="Related project id")
    amount: float = Field(..., ge=0)
    transactionId: Optional[str] = Field(None, description="Manual transaction reference")
    paymentProofURL: Optional[str] = Field(None, description="URL to payment proof image/screenshot")
    verified: bool = False
    verifiedBy: Optional[str] = None
    verifiedDate: Optional[datetime] = None

class Message(BaseModel):
    fromUserId: str
    toUserId: str
    content: str

# Response helpers (optional wrappers)
class IdResponse(BaseModel):
    id: str
