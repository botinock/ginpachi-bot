from os import getenv
from aiogram.filters import Filter
from aiogram.types import Message



ADMIN_ID = getenv('ADMIN_ID')


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == int(ADMIN_ID)

