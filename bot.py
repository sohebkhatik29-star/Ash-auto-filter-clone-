import asyncio
import logging
import logging.config
from datetime import date, datetime

import pytz
from aiohttp import web
from pyrogram import idle

from config import LOG_CHANNEL, ON_HEROKU, CLONE_MODE, PORT
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

async def start():
    print("\n")
    print("Initializing ASH FILE STORE & CLONE MANAGER BOT")

    # StreamBot already uses Pyrogram Smart Plugins with root='plugins'.
    # Do not manually import plugins after start; Pyrogram loads them during
    # initialize(). Manual re-importing can register duplicate handlers and
    # cause command handlers to be skipped.
    await StreamBot.start()

    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
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
