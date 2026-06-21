from fastapi import FastAPI
from app.db.database import Base, engine
# from app.models import User, Session, ChatHistory
from app.routes.user import router as user_router
from app.routes.session import router as session_router
from app.routes.chat import router as chat_router
from app.routes.telegram import router as telegram_router

app = FastAPI(title="NITC Nexus Backend")

Base.metadata.create_all(bind=engine)

app.include_router(user_router)
app.include_router(session_router)
app.include_router(chat_router)
app.include_router(telegram_router)

@app.get("/")
def root():
    return {"message": "Backend running"}


