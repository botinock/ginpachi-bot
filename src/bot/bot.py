from google import genai

from aiogram import Bot, Router, html

from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

from bot.anti_flood import AntiFloodMiddleware
from llm.answer import write_answer


client = genai.Client().aio
router = Router()
router.message.middleware(AntiFloodMiddleware(rate_limit=5.0))


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")

@router.message(Command('explain', 'ex'))
async def command_explain_handler(message: Message, command: CommandObject) -> None:
    text = command.args or (message.reply_to_message.text if message.reply_to_message else None)
    if not text:
        await message.reply("Введи слово, яке треба пояснити.")
        return
    answer = await write_answer(client, text)
    await message.reply(answer)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='explain', description='Explain a word'),
        BotCommand(command='ex', description='Explain a word')
        ]
    return await bot.set_my_commands(commands, BotCommandScopeDefault())
