from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.models.user import User
from app.database.session import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Retrieve user settings
    return {
        "theme": "dark",
        "notifications": True,
        "language": "en"
    }

@router.put("/")
def update_settings(
    settings_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # In a full implementation, we would save these to a user.preferences JSON field.
    return {"message": "Settings updated successfully", "data": settings_data}
