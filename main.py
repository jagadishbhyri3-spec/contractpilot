"""ContractPilot - AI Contract Negotiation Agent Micro SaaS.

Inspired by Markups.ai from Google Cloud's 1,302 AI Use Cases.
Built with FastAPI, Gemini 2.5 Pro, and Stripe.
"""
import os
import shutil
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request, File, UploadFile, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from PyPDF2 import PdfReader

from app.database import engine, Base, get_db
from app.models import User, Contract, Clause, UserTier
from app.schemas import UserCreate, UserLogin, UserResponse, ContractResponse
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_active_user, get_current_user
)
from app.ai_service import analyze_contract
from app.stripe_service import create_checkout_session, handle_webhook
from app.dependencies import require_pro_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ContractPilot", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== AUTH API ====================

@app.post("/api/auth/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        tier=UserTier.FREE,
        analyses_used=0,
        analyses_limit=1
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token({"sub": str(db_user.id)})
    return {"access_token": token, "token_type": "bearer", "user": db_user}


@app.post("/api/auth/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


# ==================== CONTRACT API ====================

@app.post("/api/contracts/analyze")
async def analyze_contract_endpoint(
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_pro_user),
    db: Session = Depends(get_db)
):
    """Upload and analyze a contract."""
    if not file.filename.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files supported")

    # Save file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{current_user.id}_{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text
    try:
        if file.filename.endswith(".pdf"):
            reader = PdfReader(file_path)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")

    if len(text) < 100:
        raise HTTPException(status_code=400, detail="Contract text too short or unreadable")

    # Create contract record
    contract = Contract(
        title=title,
        filename=safe_filename,
        original_text=text[:50000],  # Limit storage
        status="analyzing",
        owner_id=current_user.id
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    # Call AI analysis
    try:
        result = await analyze_contract(text[:15000])  # Send first 15k chars

        contract.risk_score = result["overall_risk_score"]
        contract.status = "completed"

        for clause_data in result["clauses"]:
            clause = Clause(
                contract_id=contract.id,
                clause_type=clause_data["clause_type"],
                original_text=clause_data["original_text"][:2000],
                risk_level=clause_data["risk_level"],
                explanation=clause_data["explanation"],
                suggested_revision=clause_data.get("suggested_revision", "")[:2000]
            )
            db.add(clause)

        # Increment usage for free users
        if current_user.tier.value == "free":
            current_user.analyses_used += 1

        db.commit()

    except Exception as e:
        contract.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return {"redirect": f"/contracts/{contract.id}"}


@app.get("/api/contracts", response_model=List[ContractResponse])
def list_contracts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    contracts = db.query(Contract).filter(Contract.owner_id == current_user.id).order_by(Contract.created_at.desc()).all()
    return contracts


@app.get("/api/contracts/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.owner_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.delete("/api/contracts/{contract_id}")
def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(Contract.id == contract_id, Contract.owner_id == current_user.id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Delete file
    file_path = os.path.join(UPLOAD_DIR, contract.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(contract)
    db.commit()
    return {"status": "deleted"}


# ==================== PAYMENTS API ====================

@app.post("/api/payments/checkout")
def create_payment_session(
    current_user: User = Depends(get_current_active_user)
):
    """Create Stripe checkout session for Pro upgrade."""
    session = create_checkout_session(current_user.id, current_user.email)
    return session


@app.post("/api/payments/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    result = handle_webhook(payload, sig_header)

    if result["type"] == "checkout.completed":
        user = db.query(User).filter(User.id == result["user_id"]).first()
        if user:
            user.tier = UserTier.PRO
            user.analyses_limit = 999999
            user.stripe_customer_id = result["customer_id"]
            user.stripe_subscription_id = result["subscription_id"]
            db.commit()

    elif result["type"] == "subscription.cancelled":
        user = db.query(User).filter(User.stripe_subscription_id == result["subscription_id"]).first()
        if user:
            user.tier = UserTier.FREE
            user.analyses_limit = 1
            user.stripe_subscription_id = None
            db.commit()

    return {"status": "ok"}


# ==================== HTML PAGES ====================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/contracts/{contract_id}", response_class=HTMLResponse)
def analysis_page(request: Request, contract_id: int):
    return templates.TemplateResponse("analysis.html", {"request": request, "contract_id": contract_id})


@app.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request):
    stripe_pk = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    return templates.TemplateResponse("pricing.html", {"request": request, "stripe_pk": stripe_pk})


@app.get("/pricing/success", response_class=HTMLResponse)
def pricing_success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
