from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.pending_user import PendingTelegramUser
from app.schemas.chat import ChatCreate
from app.routes.chat import chat
from app.services.telegram_service import send_telegram_message

router = APIRouter(
    prefix="/api/webhook",
    tags=["Telegram"]
)


@router.post("/telegram")
async def telegram_webhook(payload: dict, db: Session = Depends(get_db)):

    message = payload.get("message", {})
    telegram_user = message.get("from", {})
    telegram_id = str(telegram_user.get("id"))
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")

    if not text:
        return {"status": "ignored"}

    # Step 1: Check if fully registered user exists
    user = db.query(User).filter(
        User.telegram_id == telegram_id
    ).first()

    if user:
        session = db.query(SessionModel).filter(
            SessionModel.user_id == user.id,
            SessionModel.is_active == True
        ).first()

        if not session:
            session = SessionModel(user_id=user.id)
            db.add(session)
            db.commit()
            db.refresh(session)

        chat_payload = ChatCreate(
            user_id=user.id,
            session_id=session.id,
            message=text
        )

        response = await chat(chat_payload, db)

        await send_telegram_message(
            chat_id=chat_id,
            text=response.assistant_message
        )

        return {"status": "success"}

    # Step 2: Check pending onboarding
    pending_user = db.query(PendingTelegramUser).filter(
        PendingTelegramUser.telegram_id == telegram_id
    ).first()

    # Start onboarding
    if not pending_user:
        pending_user = PendingTelegramUser(
            telegram_id=telegram_id,
            current_step="waiting_roll"
        )

        db.add(pending_user)
        db.commit()

        await send_telegram_message(
            chat_id,
            "Welcome to Nexus! Please enter your roll number:"
        )

        return {"status": "onboarding_started"}

    # Step 3: Process onboarding steps
    if pending_user.current_step == "waiting_roll":
        existing_user = db.query(User).filter(
            User.roll_number == text
        ).first()

        # Existing app user
        if existing_user:
            existing_user.telegram_id = telegram_id
            db.commit()

            db.delete(pending_user)
            db.commit()

            await send_telegram_message(
                chat_id,
                "Telegram linked successfully. You can now start chatting!"
            )

            return {"status": "linked_existing_user"}

        # New Telegram-only user
        pending_user.roll_number = text
        pending_user.current_step = "waiting_name"
        db.commit()

        await send_telegram_message(
            chat_id,
            "Enter your name:"
        )

        return {"status": "waiting_name"}

    elif pending_user.current_step == "waiting_name":
        pending_user.name = text
        pending_user.current_step = "waiting_branch"
        db.commit()

        await send_telegram_message(
            chat_id,
            "Enter your branch:"
        )

        return {"status": "waiting_branch"}

    elif pending_user.current_step == "waiting_branch":
        pending_user.branch = text
        pending_user.current_step = "waiting_semester"
        db.commit()

        await send_telegram_message(
            chat_id,
            "Enter your semester (1-8):"
        )

        return {"status": "waiting_semester"}

    elif pending_user.current_step == "waiting_semester":
        new_user = User(
            telegram_id=telegram_id,
            roll_number=pending_user.roll_number,
            name=pending_user.name,
            branch=pending_user.branch,
            semester=int(text)
        )

        db.add(new_user)
        db.commit()

        db.delete(pending_user)
        db.commit()

        await send_telegram_message(
            chat_id,
            "Registration complete! You can now start chatting."
        )

        return {"status": "registered_new_user"}

    return {"status": "unknown"}