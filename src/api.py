from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
import json

from src.database import init_db, get_db, User, Ticket, Decision
from src.auth import hash_password, verify_password, create_access_token
from src.schemas import UserRegister, UserLogin, UserOut, TokenOut, TicketCreate, TicketOut
from src.deps import get_current_user
from src.decision import make_decision

app = FastAPI(title="AI Support Ticket Decision API")


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(subject=user.email)
    return TokenOut(access_token=token)


@app.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a ticket for the current user, runs the AI decision pipeline
    against it, and persists both the ticket and the resulting decision.
    """
    ticket = Ticket(user_id=current_user.id, message=payload.message)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    ai_result = make_decision(payload.message)

    decision = Decision(
        ticket_id=ticket.id,
        action=ai_result.action,
        reason=ai_result.reason,
        confidence=ai_result.confidence,
        sources=json.dumps(ai_result.sources),
    )
    db.add(decision)
    db.commit()
    db.refresh(ticket)

    return ticket


@app.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns only the current user's tickets."""
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return tickets


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns a single ticket. Enforces authorization: a user can only
    access their own tickets, even if the ticket ID exists for another user.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket