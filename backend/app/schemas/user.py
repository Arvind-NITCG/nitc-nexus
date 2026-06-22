from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str
    roll_number: str
    branch: str
    semester: int = Field(..., ge=1, le=8)


class UserResponse(BaseModel):
    id: int
    name: str
    roll_number: str
    branch: str
    semester: int
    telegram_id: str | None = None

    class Config:
        from_attributes = True