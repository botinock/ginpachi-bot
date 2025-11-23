from os import getenv

from google import genai

from aiogram import Bot, Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


from bot.anti_flood import AntiFloodMiddleware
from bot.filters import IsAdmin
from bot.message_processor import MessageProcessor
from bot.help import help_message, start_message
from bot.user_processor import UserProcessor

from db.client import get_db_client
from db.models import UserRole
from db.user_repository import UserRepository

from llm.answer import write_answer

BOT_TOKEN = getenv("BOT_TOKEN")
ADMIN_ID = getenv('ADMIN_ID')

llm_client = genai.Client().aio
db_client = get_db_client()
user_repository = UserRepository(db_client)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

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
    user_id = UserProcessor.get_user_id_from_message(message)
    user = await user_repository.get_user(user_id)
    if not user:
        user = UserProcessor.create_user_from_message(message)
        await user_repository.create_user(user)
        await bot.send_message(ADMIN_ID, f"Новий юзер! {user.user_id} (@{user.username})")
    
    if user.username != message.from_user.username:
        user = UserProcessor.update_user_username(user, message)
        await user_repository.update_user(user)
    
    if user.updated_at is None or user.updated_at.date() < message.date.date():
        await user_repository.reset_daily_limit(user.user_id)
        user.request_count = 0
    
    can_make_request, error_message = UserProcessor.can_user_make_request(user)
    if not can_make_request:
        await message.reply(error_message)
        return

    text = MessageProcessor.process_message(message, command)
    if not text:
        await message.reply("Введи слово, яке треба пояснити.")
        return
    answer = await write_answer(llm_client, text)
    await message.reply(answer)
    await user_repository.increment_request_count(user.user_id)


@router.message(Command('profile'))
async def command_profile_handler(message: Message) -> None:
    user_id = UserProcessor.get_user_id_from_message(message)
    user = await user_repository.get_user(user_id)
    if not user:
        await message.answer("В тебе ще немає профілю.")
        return
    
    if user.username != message.from_user.username:
        user = UserProcessor.update_user_username(user, message)
        await user_repository.update_user(user)
    
    profile_text = UserProcessor.get_user_profile_text(user)
    await message.answer(profile_text)


@router.message(Command('top_users'), IsAdmin())
async def command_top_requests_handler(message: Message) -> None:
    top_users = await user_repository.list_top_users_by_requests(limit=10)
    response_lines = ["Топ користувачів за загальною кількістю запитів:"]
    for idx, user in enumerate(top_users, start=1):
        username_display = f"@{user.username}" if user.username else f"User ID: {user.user_id}"
        response_lines.append(f"{idx}. {username_display}: {user.total_requests_lifetime}")
    response_text = "\n".join(response_lines)
    await message.answer(response_text)


@router.message(Command('top_users_today'), IsAdmin())
async def command_top_daily_requests_handler(message: Message) -> None:
    top_users = await user_repository.list_top_users_by_daily_requests(limit=10)
    response_lines = ["Топ користувачів за кількістю запитів сьогодні:"]
    for idx, user in enumerate(top_users, start=1):
        username_display = f"@{user.username}" if user.username else f"User ID: {user.user_id}"
        response_lines.append(f"{idx}. {username_display}: {user.request_count}")
    response_text = "\n".join(response_lines)
    await message.answer(response_text)


@router.message(Command('set_role'), IsAdmin())
async def command_set_role_handler(message: Message, command: CommandObject) -> None:
    role = command.args
    if role not in UserRole.__members__.values():
        await message.reply(f"Невідома роль. Доступні ролі: {', '.join(UserRole.__members__.values())}")
        return
    if not message.reply_to_message:
        await message.reply("Щоб встановити роль, відповідай на повідомлення користувача.")
        return
    target_user_id = message.reply_to_message.from_user.id
    await user_repository.set_role(target_user_id, role)
    await message.answer("Зроблено.")


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='help', description='Викликати підказку'),
        BotCommand(command='word', description='Пояснити японське слово українською'),
        BotCommand(command='profile', description='Твій профіль'),
        ]
    return await bot.set_my_commands(commands, BotCommandScopeDefault())
