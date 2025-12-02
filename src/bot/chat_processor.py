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
            chat_id=message.chat.id,
            chat_name=message.chat.title,
            chat_username=message.chat.username
        )

    @staticmethod
    def update_chat_title_and_username(chat: Chat, message: Message) -> Chat:
        chat.chat_name = message.chat.title
        chat.chat_username = message.chat.username
        return chat

    @staticmethod
    def get_chat_username_from_message(message: Message) -> str | None:
        return message.chat.username
    
    @staticmethod
    def get_chat_name_from_message(message: Message) -> str | None:
        return message.chat.title
