from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, HTTPException, status
# Import our modules
import models
import schemas
from database import engine, get_db
from workers.mail_worker import MailWorker

# Create tables automatically
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Enable CORS for React (Port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for dev; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

worker = MailWorker()

@app.post("/connect", response_model=schemas.APIResponse)
def connect_bank(
    request: schemas.UserConnectRequest, 
    db: Session = Depends(get_db)
):
    # 1. Check if Username exists
    if db.query(models.User).filter(models.User.username == request.username).first():
        raise HTTPException(
            status_code=400, 
            detail="Username already taken. Please choose another."
        )

    # 2. Check if Email exists
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    if not user:
        # Create new User with username
        user = models.User(
            username=request.username,  # <--- Save it here
            email=request.email,
            imap_user=request.email,
            imap_password=request.password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Optional: Handle case where email exists but they want to update/link username
        # For now, let's just update the password
        user.imap_password = request.password
        db.commit()

    # Trigger the background worker
    worker.start_onboarding(user.id)
    
    return {
        "status": "success",
        "message": f"Welcome, {request.username}! Sync started."
    }