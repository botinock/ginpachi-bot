import asyncio
import logging
import sys
from os import getenv
from google import genai

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from bot.anti_flood import AntiFloodMiddleware
from llm.answer import write_answer

# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("BOT_TOKEN")

# All handlers should be attached to the Router (or Dispatcher)

client = genai.Client().aio
dp = Dispatcher()
dp.message.middleware(AntiFloodMiddleware(rate_limit=5.0))


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")

@dp.message(Command('explain', 'ex'))
async def command_explain_handler(message: Message, command: CommandObject) -> None:
    text = command.args or (message.reply_to_message.text if message.reply_to_message else None)
    if not text:
        await message.reply("Введи слово, яке треба пояснити.")
        return
    answer = await write_answer(client, text)
    await message.reply(answer)

async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())