from aiogram.types import Message
from db.models import Chat

class ChatProcessor:
    @staticmethod
    def get_chat_id_from_message(message: Message) -> int | None:
        if message.chat.type != "private":
            return message.chat.id
    
    @staticmethod
    def create_chat_from_message(message: Message) -> Chat:
        return Chat(
            chat_id=message.chat.id
        )
