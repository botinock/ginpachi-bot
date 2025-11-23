from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable
import time

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit  # Time in seconds between requests
        self.users_last_request = {}  # Stores last request time for each user

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            user_id = event.from_user.id
            now = time.time()

            if user_id in self.users_last_request:
                last_request_time = self.users_last_request[user_id]
                if (now - last_request_time) < self.rate_limit:
                    # User is sending requests too fast
                    # await event.answer(f"Please wait {self.rate_limit - (now - last_request_time):.2f} seconds before sending another message.")
                    await event.answer("Зачекай")
                    return  # Stop processing the event
            
            self.users_last_request[user_id] = now
        
        return await handler(event, data)
