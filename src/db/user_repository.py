from datetime import datetime, timezone
from os import getenv

from google.cloud.firestore import AsyncClient, Increment

from db.models import ROLE_LIMITS, User, UserRole


class UserRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.collection = self.client.collection(getenv('USERS_COLLECTION'))

    async def get_user(self, user_id: int) -> User | None:
        doc = await self.collection.document(str(user_id)).get()
        if doc.exists:
            return User.model_validate(doc.to_dict())

    async def create_user(self, user: User) -> None:
        await self.collection.document(str(user.user_id)).set(user.model_dump())

    async def update_user(self, user: User) -> None:
        await self.collection.document(str(user.user_id)).update(user.model_dump())

    async def delete_user(self, user_id: int) -> None:
        await self.collection.document(str(user_id)).delete()

    async def increment_request_count(self, user_id: int, increment: int = 1) -> None:
        user_ref = self.collection.document(str(user_id))
        await user_ref.update({
            'request_count': Increment(increment),
            'total_requests_lifetime': Increment(increment),
            'updated_at': datetime.now(timezone.utc),
        })

    async def reset_daily_limit(self, user_id: int) -> None:
        user_ref = self.collection.document(str(user_id))
        await user_ref.update({
            'request_count': 0,
            'updated_at': datetime.now(timezone.utc)
        })

    async def set_daily_limit(self, user_id: int, daily_limit: int) -> None:
        user_ref = self.collection.document(str(user_id))
        await user_ref.update({
            'daily_limit': daily_limit,
            'updated_at': datetime.now(timezone.utc)
        })

    async def set_role(self, user_id: int, role: str) -> None:
        user_ref = self.collection.document(str(user_id))
        await user_ref.update({
            'role': role,
            'daily_limit': ROLE_LIMITS.get(role, ROLE_LIMITS[UserRole.USER]),
            'updated_at': datetime.now(timezone.utc)
        })

    async def list_top_users_by_requests(self, limit: int = 10) -> list[User]:
        query = self.collection.order_by('total_requests_lifetime', direction='DESCENDING').limit(limit)
        users: list[User] = []
        async for doc in query.stream():
            users.append(User.model_validate(doc.to_dict()))
        return users

    async def list_top_users_by_daily_requests(self, limit: int = 10) -> list[User]:
        query = self.collection.order_by('request_count', direction='DESCENDING').limit(limit)
        users: list[User] = []
        async for doc in query.stream():
            users.append(User.model_validate(doc.to_dict()))
        return users

