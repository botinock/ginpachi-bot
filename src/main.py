import logging
from os import getenv
import sys
from aiogram import Bot, Dispatcher
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.bot import router, set_commands

ADMIN_ID = getenv('ADMIN_ID')
BOT_TOKEN = getenv("BOT_TOKEN")
HOST = getenv("HOST")
PORT = int(getenv("PORT"))
WEBHOOK_PATH = getenv("WEBHOOK_PATH")
BASE_URL = getenv("BASE_URL")
WEBHOOK_SECRET_TOKEN = getenv("WEBHOOK_SECRET_TOKEN")

async def on_startup(bot: Bot) -> None:
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, "Bot started!")
    set_success = await set_commands(bot)
    await bot.send_message(ADMIN_ID, f"Starting commands success: {set_success}")
    await bot.set_webhook(f"{BASE_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET_TOKEN)

async def on_shutdown(bot: Bot) -> None:
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, "Bot stopped!")
    # await bot.delete_webhook(drop_pending_updates=True)
    # await bot.session.close()

def main() -> None:
    # Dispatcher is a root router
    dp = Dispatcher()
    # ... and all other routers should be attached to Dispatcher
    dp.include_router(router)

    # Register startup hook to initialize webhook
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Create aiohttp.web.Application instance
    app = web.Application()

    # Create an instance of request handler,
    # aiogram has few implementations for different cases of usage
    # In this example we use SimpleRequestHandler which is designed to handle simple cases
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET_TOKEN,
    )
    # Register webhook handler on application
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Mount dispatcher startup and shutdown hooks to aiohttp application
    setup_application(app, dp, bot=bot)

    # And finally start webserver
    web.run_app(app, host=HOST, port=PORT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main()
