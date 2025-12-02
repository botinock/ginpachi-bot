from datetime import datetime, timezone
from os import getenv

from google.cloud.firestore import AsyncClient, Increment

from db.models import Chat


class ChatRepository:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.collection = self.client.collection(getenv('CHAT_COLLECTION'))
    
    async def get_chat(self, chat_id: int) -> dict | None:
        doc = await self.collection.document(str(chat_id)).get()
        if doc.exists:
            return doc.to_dict()
    
    async def create_chat(self, chat: Chat) -> None:
        await self.collection.document(str(chat.chat_id)).set(chat.model_dump())
    
    async def update_chat(self, chat_id: int, chat_data: dict) -> None:
        await self.collection.document(str(chat_id)).update(chat_data)
    
    async def delete_chat(self, chat_id: int) -> None:
        await self.collection.document(str(chat_id)).delete()
    
    async def list_chats(self, limit: int = 10) -> list[dict]:
        query = self.collection.limit(limit)
        chats: list[dict] = []
        async for doc in query.stream():
            chats.append(doc.to_dict())
        return chats
    
    async def increment_message_count(self, chat_id: int, increment: int = 1) -> None:
        chat_ref = self.collection.document(str(chat_id))
        await chat_ref.update({
            'message_count': Increment(increment),
            'updated_at': datetime.now(timezone.utc),
        })
    
    async def reset_message_count(self, chat_id: int) -> None:
        chat_ref = self.collection.document(str(chat_id))
        await chat_ref.update({
            'message_count': 0,
            'updated_at': datetime.now(timezone.utc)
        })
    
    async def list_top_chats_by_messages(self, limit: int = 10) -> list[dict]:
        query = self.collection.order_by('message_count', direction='DESCENDING').limit(limit)
        chats: list[dict] = []
        async for doc in query.stream():
            chats.append(doc.to_dict())
        return chats
