import asyncio
import logging
import logging.config
from datetime import date, datetime

import pytz
from aiohttp import web
from pyrogram import idle
from pyrogram.types import BotCommand, BotCommandScopeChat

from config import LOG_CHANNEL, ON_HEROKU, CLONE_MODE, PORT, ADMINS
from Script import script
from AshCore.server import web_server
from AshCore.bot import StreamBot
from AshCore.bot.clients import initialize_clients
from AshCore.utils.keepalive import ping_server
from plugins.clone import restart_bots

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

loop = asyncio.get_event_loop()

async def setup_main_menu():
    user_commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("link", "Create a shareable file link"),
        BotCommand("api", "Set or view shortener API"),
        BotCommand("base_site", "Set or view shortener site"),
        BotCommand("clone", "Create your own clone bot"),
    ]
    admin_commands = user_commands + [
        BotCommand("broadcast", "Broadcast a message to users"),
        BotCommand("deletecloned", "Remove a cloned bot record"),
    ]
    try:
        await StreamBot.set_bot_commands(user_commands)
        for admin in ADMINS:
            try:
                admin_id = int(admin)
                await StreamBot.set_bot_commands(
                    admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_id),
                )
            except (TypeError, ValueError):
                continue
            except Exception:
                logging.exception("Unable to set admin command menu for %s", admin)
    except Exception:
        logging.exception("Unable to set main bot command menu")

async def start():
    print("\n")
    print("Initializing ASH FILE STORE & CLONE MANAGER BOT")

    # StreamBot uses Pyrogram Smart Plugins with root='plugins'.
    await StreamBot.start()

    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
    await setup_main_menu()
    await initialize_clients()

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")

    app = web.AppRunner(await web_server())
    try:
        await StreamBot.send_message(
            chat_id=LOG_CHANNEL,
            text=script.RESTART_TXT.format(today, time)
        )
    except Exception as e:
        logging.warning("Unable to send restart log: %s", e)

    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, int(PORT)).start()

    if CLONE_MODE is True:
        await restart_bots()

    print("Bot Started - ASH FILE STORE & CLONE MANAGER")
    await idle()

if __name__ == '__main__':
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
