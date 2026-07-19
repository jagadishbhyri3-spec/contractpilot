"""Shared dependencies."""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_active_user
from app.models import User


def require_pro_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure user has Pro tier or available free analyses."""
    if current_user.tier.value == "free" and current_user.analyses_used >= current_user.analyses_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free analysis limit reached. Upgrade to Pro for unlimited analyses."
        )
    return current_user
