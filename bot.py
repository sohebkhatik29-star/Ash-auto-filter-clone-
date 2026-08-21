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
from clone_plugins.clone_manager_fix import register_clone_manager_navigation

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('pyrogram').setLevel(logging.ERROR)
loop = asyncio.get_event_loop()


def all_commands():
    return [
        BotCommand('start', 'Start the bot'),
        BotCommand('help', 'Show all commands'),
        BotCommand('link', 'Create a shareable file link'),
        BotCommand('genlink', 'Generate a file link'),
        BotCommand('getlink', 'Generate a file link'),
        BotCommand('batch', 'Create batch links'),
        BotCommand('custom_batch', 'Create custom batch links'),
        BotCommand('special_link', 'Create a special link'),
        BotCommand('universal_link', 'Create a universal link'),
        BotCommand('shortener', 'Link shortener'),
        BotCommand('settings', 'Customize settings'),
        BotCommand('api', 'Set or view shortener API'),
        BotCommand('base_site', 'Set or view shortener site'),
        BotCommand('clone', 'Create your own clone'),
    ]


def owner_commands():
    return all_commands() + [
        BotCommand('admin', 'Open owner admin panel'),
        BotCommand('stats', 'Show statistics'),
        BotCommand('broadcast', 'Broadcast a message'),
        BotCommand('ban', 'Ban a user'),
        BotCommand('unban', 'Unban a user'),
        BotCommand('force_sub', 'Set Force Subscribe'),
        BotCommand('caption', 'Set Custom Caption'),
        BotCommand('button', 'Add Custom Button'),
        BotCommand('protect', 'Protect Content'),
        BotCommand('auto_delete', 'Auto delete delivered files'),
        BotCommand('no_forward', 'Disable forwarding'),
        BotCommand('moderator', 'Manage moderators'),
        BotCommand('access_token', 'Access token settings'),
        BotCommand('transfer_db', 'Transfer users'),
        BotCommand('deactivate', 'Deactivate or activate clone'),
        BotCommand('mode', 'Public/private mode'),
        BotCommand('restart', 'Save and restart'),
        BotCommand('delete', 'Delete clone record'),
        BotCommand('start_msg', 'Set start message'),
        BotCommand('deletecloned', 'Remove a cloned bot record'),
    ]


async def setup_main_menu():
    try:
        await StreamBot.set_bot_commands(all_commands())
        for admin in ADMINS:
            try:
                await StreamBot.set_bot_commands(
                    owner_commands(),
                    scope=BotCommandScopeChat(chat_id=int(admin)),
                )
            except Exception:
                logging.exception('Unable to set admin menu for %s', admin)
    except Exception:
        logging.exception('Unable to set main command menu')


async def start():
    print('\nInitializing ASH FILE STORE & CLONE MANAGER BOT')
    await StreamBot.start()
    register_clone_manager_navigation(StreamBot, master=True)
    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username
    try:
        from plugins.master_settings import register as register_master_settings
        from clone_plugins.commands import register as register_commands
        from clone_plugins.advanced import register as register_advanced
        from clone_plugins.single_link import register as register_single_link
        from clone_plugins.custom_batch import register as register_custom_batch
        from clone_plugins.channel_batch import register as register_channel_batch
        from clone_plugins.special_link import register as register_special_link
        register_master_settings(StreamBot)
        register_commands(StreamBot)
        register_advanced(StreamBot)
        # The master bot also supports the same interactive single-link flow.
        register_single_link(StreamBot)
        # Custom batch, channel batch, and special link must run with high priority and stop propagation
        register_custom_batch(StreamBot, base_group=-101)
        register_channel_batch(StreamBot, base_group=-102)
        register_special_link(StreamBot, base_group=-103)
        logging.info('ASH master command handlers loaded successfully')
    except Exception:
        logging.exception('Unable to load ASH master command handlers')
    await setup_main_menu()
    await initialize_clients()
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today(); now = datetime.now(tz); time = now.strftime('%H:%M:%S %p')
    app = web.AppRunner(await web_server())
    try:
        await StreamBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time))
    except Exception as e:
        logging.warning('Unable to send restart log: %s', e)
    await app.setup()
    await web.TCPSite(app, '0.0.0.0', int(PORT)).start()
    if CLONE_MODE:
        await restart_bots()
    print('Bot Started - ASH FILE STORE & CLONE MANAGER')
    await idle()


if __name__ == '__main__':
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')