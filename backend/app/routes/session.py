from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.session import Session as SessionModel
from app.models.chat import ChatHistory
from app.models.user import User
from app.schemas.session import SessionCreate, SessionResponse
from app.schemas.chat import ChatResponse

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])

@router.post("/", response_model=SessionResponse)
def create_session(session: SessionCreate, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.id == session.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_session = SessionModel(user_id=session.user_id)

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session

@router.get("/{session_id}/history", response_model=list[ChatResponse])
def get_session_history(session_id: int, db: Session = Depends(get_db)):

    session = db.query(SessionModel).filter(
        SessionModel.id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    chats = db.query(ChatHistory).filter(
        ChatHistory.session_id == session_id
    ).order_by(ChatHistory.timestamp.asc()).all()

    return chats