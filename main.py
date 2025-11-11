import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Project, Payment, Message

app = FastAPI(title="A&V TechSolutions – Student Project Portal API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static uploads
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def to_str_id(doc):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    # Convert datetime to isoformat
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "A&V TechSolutions Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            try:
                cols = db.list_collection_names()
                response["collections"] = cols[:10]
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Auth-like simple endpoints (demo only)
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr


@app.post("/api/register")
def register_user(payload: RegisterRequest):
    # If exists, just return existing
    existing = db["user"].find_one({"email": payload.email}) if db else None
    if existing:
        return {"id": str(existing["_id"]), "name": existing.get("name"), "email": existing.get("email"), "role": existing.get("role", "student")}
    data = User(name=payload.name, email=payload.email, role="student")
    new_id = create_document("user", data)
    return {"id": new_id, "name": data.name, "email": data.email, "role": data.role}


class LoginRequest(BaseModel):
    email: EmailStr


@app.post("/api/login")
def login_user(payload: LoginRequest):
    user = db["user"].find_one({"email": payload.email}) if db else None
    if not user:
        # auto-register as student
        data = User(name=payload.email.split("@")[0].title(), email=payload.email, role="student")
        new_id = create_document("user", data)
        return {"id": new_id, "name": data.name, "email": data.email, "role": data.role}
    return {"id": str(user["_id"]), "name": user.get("name"), "email": user.get("email"), "role": user.get("role", "student")}


@app.get("/api/user/{user_id}")
def get_user(user_id: str):
    try:
        doc = db["user"].find_one({"_id": ObjectId(user_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="User not found")
        return to_str_id(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")


@app.get("/api/users")
def list_users(role: Optional[str] = None):
    filt = {"role": role} if role else {}
    docs = db["user"].find(filt).sort("created_at", -1)
    return [to_str_id(d) for d in docs]


# Projects
class ProjectCreate(BaseModel):
    studentId: str
    title: str
    technology: str
    description: Optional[str] = None
    fileUrl: Optional[str] = None


@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    # Validate technology to schema allowed list via Project model
    proj = Project(
        studentId=payload.studentId,
        title=payload.title,
        technology=payload.technology,  # Pydantic will validate choices
        description=payload.description,
    )
    new_id = create_document("project", proj)
    # attach initial file if provided
    if payload.fileUrl:
        db["project"].update_one({"_id": ObjectId(new_id)}, {"$addToSet": {"deliverables": payload.fileUrl}})
    created = db["project"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(created)


@app.get("/api/projects")
def list_projects(studentId: Optional[str] = None):
    filt = {"studentId": studentId} if studentId else {}
    docs = db["project"].find(filt).sort("created_at", -1)
    return [to_str_id(d) for d in docs]


class ProjectUpdate(BaseModel):
    status: Optional[str] = None
    paymentStatus: Optional[str] = None
    adminRemarks: Optional[str] = None
    deliverables: Optional[List[str]] = None


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    try:
        update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
        if not update:
            return {"updated": False}
        update["updated_at"] = datetime.now(timezone.utc)
        res = db["project"].update_one({"_id": ObjectId(project_id)}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        doc = db["project"].find_one({"_id": ObjectId(project_id)})
        return to_str_id(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")


# Payments
class PaymentCreate(BaseModel):
    studentId: str
    projectId: Optional[str] = None
    amount: float
    transactionId: Optional[str] = None
    paymentProofURL: Optional[str] = None


@app.post("/api/payments")
def create_payment(payload: PaymentCreate):
    pay = Payment(
        studentId=payload.studentId,
        projectId=payload.projectId,
        amount=payload.amount,
        transactionId=payload.transactionId,
        paymentProofURL=payload.paymentProofURL,
    )
    new_id = create_document("payment", pay)
    created = db["payment"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(created)


@app.get("/api/payments")
def list_payments(studentId: Optional[str] = None):
    filt = {"studentId": studentId} if studentId else {}
    docs = db["payment"].find(filt).sort("created_at", -1)
    return [to_str_id(d) for d in docs]


class PaymentUpdate(BaseModel):
    verified: Optional[bool] = None
    verifiedBy: Optional[str] = None
    verifiedDate: Optional[datetime] = None


@app.patch("/api/payments/{payment_id}")
def update_payment(payment_id: str, payload: PaymentUpdate):
    try:
        update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
        if not update:
            return {"updated": False}
        update["updated_at"] = datetime.now(timezone.utc)
        res = db["payment"].update_one({"_id": ObjectId(payment_id)}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Payment not found")
        doc = db["payment"].find_one({"_id": ObjectId(payment_id)})
        return to_str_id(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payment id")


# Messages
class MessageCreate(BaseModel):
    fromUserId: str
    toUserId: str
    content: str


@app.post("/api/messages")
def send_message(payload: MessageCreate):
    msg = Message(**payload.model_dump())
    new_id = create_document("message", msg)
    created = db["message"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(created)


@app.get("/api/messages")
def list_messages(userId: str):
    # Fetch messages where user is sender or receiver
    docs = db["message"].find({"$or": [{"fromUserId": userId}, {"toUserId": userId}]}).sort("created_at", -1)
    return [to_str_id(d) for d in docs]


# File upload for payment proof or deliverables
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    filename = f"{datetime.now(timezone.utc).timestamp()}_{file.filename}"
    safe_name = filename.replace("..", "").replace("/", "_")
    path = os.path.join(UPLOAD_DIR, safe_name)
    with open(path, "wb") as buffer:
        buffer.write(file.file.read())
    url = f"/uploads/{safe_name}"
    return {"url": url}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
