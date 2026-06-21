from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.db.deps import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.chat import ChatHistory
from app.schemas.chat import ChatCreate, ChatReply
from app.services.ai_service import call_rag_engine

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"]
)


@router.post("/", response_model=ChatReply)
async def chat(payload: ChatCreate, db: Session = Depends(get_db)):

    # Validate user
    user = db.query(User).filter(
        User.id == payload.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Find active session
    session = db.query(SessionModel).filter(
        SessionModel.user_id == payload.user_id,
        SessionModel.is_active == True
    ).first()

    current_time = datetime.now(timezone.utc)

    # If session exists, check timeout
    if session:
        if session.last_activity:
            inactive_time = current_time - session.last_activity

            if inactive_time > timedelta(minutes=30):
                session.is_active = False
                db.commit()
                session = None

    # Create new session if no active session
    if not session:
        session = SessionModel(
            user_id=payload.user_id,
            is_active=True,
            last_activity=current_time
        )

        db.add(session)
        db.commit()
        db.refresh(session)

    # Fetch previous chat history
    previous_chats = db.query(ChatHistory).filter(
        ChatHistory.session_id == session.id
    ).order_by(ChatHistory.timestamp.asc()).all()

    chat_history = [
        {
            "role": chat.role,
            "content": chat.message
        }
        for chat in previous_chats
    ]

    # Store user message
    user_chat = ChatHistory(
        session_id=session.id,
        role="user",
        message=payload.message
    )

    db.add(user_chat)

    # Update session activity
    session.last_activity = current_time

    db.commit()

    # Call AI Engine
    ai_result = await call_rag_engine(
        query=payload.message,
        chat_history=chat_history,
        metadata={
            "branch": user.branch,
            "semester": user.semester
        }
    )

    ai_response = ai_result["answer"]

    # Store assistant response
    bot_chat = ChatHistory(
        session_id=session.id,
        role="assistant",
        message=ai_response
    )

    db.add(bot_chat)

    # Update activity again
    session.last_activity = datetime.now(timezone.utc)

    db.commit()

    return ChatReply(
        user_message=payload.message,
        assistant_message=ai_response
    )