from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: int


class SessionResponse(BaseModel):
    id: int
    user_id: int
    is_active: bool

    class Config:
        from_attributes = True