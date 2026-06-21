from pydantic import BaseModel
from datetime import datetime


class ChatCreate(BaseModel):
    user_id: int
    message: str


class ChatResponse(BaseModel):
    id: int
    session_id: int
    role: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ChatReply(BaseModel):
    user_message: str
    assistant_message: str