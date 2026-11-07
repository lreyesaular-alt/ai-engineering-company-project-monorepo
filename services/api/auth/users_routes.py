from fastapi import APIRouter, Depends

from .dependencies import get_current_user
from .models import UserPublic, UserListItem
from .db import get_db


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def get_my_user(current_user=Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[UserListItem])
def get_users(current_user=Depends(get_current_user)):
    db = get_db()
    try:
        return db.all()
    finally:
        db.close()
