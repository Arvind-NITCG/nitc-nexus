from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(
        User.roll_number == user.roll_number
    ).first()

    if existing_user:
        return existing_user

    new_user = User(
        name=user.name,
        roll_number=user.roll_number,
        branch=user.branch,
        semester=user.semester
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user