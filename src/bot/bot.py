from google import genai

from aiogram import Bot, Router, html

from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

from bot.anti_flood import AntiFloodMiddleware
from llm.answer import write_answer
from bot.help import help_message, start_message


client = genai.Client().aio
router = Router()
router.message.middleware(AntiFloodMiddleware(rate_limit=5.0))


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(start_message())

@router.message(Command('help'))
async def command_help_handler(message: Message) -> None:
    await message.answer(help_message())

@router.message(Command('word', 'ex'))
async def command_explain_handler(message: Message, command: CommandObject) -> None:
    text_arg = command.args
    quote_text = message.quote.text if message.reply_to_message else None
    reply_text = message.reply_to_message.text if message.reply_to_message else None
    text = text_arg or quote_text or reply_text
    if not text:
        await message.reply("Введи слово, яке треба пояснити.")
        return
    answer = await write_answer(client, text)
    await message.reply(answer)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='help', description='Викликати підказку'),
        BotCommand(command='word', description='Пояснити японське слово українською'),
        ]
    return await bot.set_my_commands(commands, BotCommandScopeDefault())
