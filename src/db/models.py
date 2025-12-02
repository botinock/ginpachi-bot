from typing import Optional
from pydantic import BaseModel, computed_field
from datetime import datetime, timezone

from enum import Enum

class UserRole(str, Enum):
    """Defines the allowed values for the user's role."""
    USER = "user"
    PREMIUM_USER = "premium_user"
    ADMIN = "admin"


ROLE_LIMITS = {
    UserRole.USER: 50,
    UserRole.PREMIUM_USER: 250,
    UserRole.ADMIN: 1000,
}


class User(BaseModel):
    user_id: int
    username: Optional[str] = None
    role: UserRole = UserRole.USER  # default role is 'user'
    request_count: int = 0
    total_requests_lifetime: int = 0
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)

    @computed_field
    @property
    def daily_limit(self) -> int:
        """Looks up the daily limit based on the user's role."""
        # Use .value to get the string key for the lookup (e.g., "admin")
        return ROLE_LIMITS.get(self.role, ROLE_LIMITS[UserRole.USER])


class Chat(BaseModel):
    chat_id: int
    message_count: int = 0
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
