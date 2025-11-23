from aiogram.types import Message
from aiogram.filters import CommandObject


class MessageProcessor:
    @staticmethod
    def process_message(message: Message, command: CommandObject) -> str:
        text_arg = command.args
        quote_text = message.quote.text if message.reply_to_message else None
        reply_text = message.reply_to_message.text if message.reply_to_message else None
        text = text_arg or quote_text or reply_text
        return text