from sqlalchemy import Column, Integer, String
from app.db.database import Base


class PendingTelegramUser(Base):
    __tablename__ = "pending_telegram_users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=False)
    current_step = Column(String, nullable=False)

    roll_number = Column(String, nullable=True)
    name = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)