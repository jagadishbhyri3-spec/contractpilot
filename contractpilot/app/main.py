from fastapi import FastAPI, Request, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import json
import stripe

from app.database import SessionLocal, engine, Base
from app.models import User, Contract, Clause
from app.schemas import UserCreate, UserLogin, ContractCreate, AnalysisResponse
from app.auth import create_access_token, verify_password, get_password_hash, get_current_user
from app.ai_service import analyze_contract
from app.dependencies import require_pro

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ContractPilot", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Stripe setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID_PRO = os.getenv("STRIPE_PRICE_ID_PRO", "")
APP_URL = os.getenv("APP_URL", "https://contractpilot-1.onrender.com")

# Dependency: get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# PAGE ROUTES (HTML pages)
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    """Render the contract analysis page with sidebar navigation."""
    return templates.TemplateResponse("analysis.html", {"request": request})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    return templates.TemplateResponse("pricing.html", {"request": request})

@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request):
    return templates.TemplateResponse("cookies.html", {"request": request})

@app.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    return templates.TemplateResponse("security.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


# ═══════════════════════════════════════════════════════════════
# AUTH API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": new_user.email})
    return {"access_token": token, "token_type": "bearer", "plan": new_user.plan}

@app.post("/api/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer", "plan": db_user.plan}


# ═══════════════════════════════════════════════════════════════
# DASHBOARD API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def dashboard_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contracts = db.query(Contract).filter(Contract.user_id == current_user.id).all()

    total_contracts = len(contracts)
    monthly_analyses = len([c for c in contracts if c.created_at and c.created_at.month == datetime.now().month])

    risk_scores = [c.risk_score for c in contracts if c.risk_score is not None]
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

    return {
        "total_contracts": total_contracts,
        "monthly_analyses": monthly_analyses,
        "avg_risk": avg_risk,
        "plan": current_user.plan,
        "contracts": [
            {
                "id": c.id,
                "filename": c.filename,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "risk_score": c.risk_score,
                "clause_count": len(c.clauses) if c.clauses else 0
            }
            for c in contracts
        ]
    }


# ═══════════════════════════════════════════════════════════════
# CONTRACT UPLOAD & ANALYSIS API
# ═══════════════════════════════════════════════════════════════

@app.post("/api/contracts/upload")
async def upload_contract(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Read file content
    content = await file.read()

    # Extract text from PDF or use raw text
    if file.filename.endswith(".pdf"):
        try:
            import PyPDF2
            from io import BytesIO
            reader = PyPDF2.PdfReader(BytesIO(content))
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception:
            text = content.decode("utf-8", errors="ignore")
    else:
        text = content.decode("utf-8", errors="ignore")

    # Save contract to DB
    contract = Contract(
        user_id=current_user.id,
        filename=file.filename,
        content=text,
        risk_score=0
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    # Run AI analysis
    analysis = analyze_contract(text)

    # Update contract with risk score
    contract.risk_score = analysis.get("risk_score", 0)
    db.commit()

    # Save clauses
    for clause_data in analysis.get("clauses", []):
        clause = Clause(
            contract_id=contract.id,
            title=clause_data.get("title", ""),
            severity=clause_data.get("severity", "LOW"),
            explanation=clause_data.get("explanation", ""),
            original_text=clause_data.get("original_text", ""),
            suggested_text=clause_data.get("suggested_text", "")
        )
        db.add(clause)

    db.commit()

    return {"contract_id": contract.id, "redirect": f"/analysis?id={contract.id}"}

@app.get("/api/contracts/{contract_id}/analysis")
async def get_analysis(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    clauses = db.query(Clause).filter(Clause.contract_id == contract_id).all()

    return {
        "risk_score": contract.risk_score,
        "clauses": [
            {
                "title": c.title,
                "severity": c.severity,
                "explanation": c.explanation,
                "original_text": c.original_text,
                "suggested_text": c.suggested_text
            }
            for c in clauses
        ]
    }


# ═══════════════════════════════════════════════════════════════
# STRIPE PAYMENTS API
# ═══════════════════════════════════════════════════════════════

@app.post("/api/payments/create-checkout-session")
async def create_checkout_session(current_user: User = Depends(get_current_user)):
    if not STRIPE_PRICE_ID_PRO:
        raise HTTPException(status_code=500, detail="Stripe price ID not configured")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID_PRO,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{APP_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_URL}/pricing",
            client_reference_id=str(current_user.id),
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payments/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for payment processing.
    Supports both test and live mode webhooks.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Fallback: parse without verification (NOT for production)
            event = json.loads(payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the event
    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"Payment successful for session: {session.get('id')}")
        # TODO: Update user plan to "pro" in database
        # user_id = session.get("client_reference_id")

    elif event_type == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        print(f"Invoice payment succeeded: {invoice.get('id')}")

    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        print(f"Invoice payment failed: {invoice.get('id')}")

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        print(f"Subscription cancelled: {subscription.get('id')}")
        # TODO: Downgrade user to free plan

    return {"status": "success", "event": event_type}
