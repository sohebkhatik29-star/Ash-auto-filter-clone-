"""Register handlers on dynamically-created Pyrogram clone clients."""

from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins import advanced as adv
from clone_plugins import clone_settings_ui as cset
from clone_plugins import single_link
from clone_plugins import custom_batch as cbatch
from clone_plugins import channel_batch as chbatch
from clone_plugins import special_link
from clone_plugins import master_manager


async def clean_help(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open this help\n"
        "• /getlink — Create a single shareable file link\n"
        "• /link — Create a single shareable file link\n"
        "• /batch — Store multiple messages from a channel\n"
        "• /custom_batch — Create custom batch links\n"
        "• /special_link — Create a special link\n"
        "• /universal_link — Create a universal link\n"
        "• /shortener — Shortener settings\n"
        "• /settings — Customize bot\n"
        "• /api KEY — Set or view shortener API\n"
        "• /base_site SITE — Set or view shortener site\n"
        "• /clone — Create your own clone\n\n"
        "👑 <b>Owner / Moderator</b>\n"
        "• /admin • /stats • /broadcast\n"
        "• /ban • /unban • /force_sub\n"
        "• /caption • /button • /protect\n"
        "• /auto_delete • /no_forward • /moderator\n"
        "• /access_token • /transfer_db • /deactivate\n"
        "• /mode • /restart • /delete • /start_msg\n\n"
        "⚙️ Owner features are also available from <b>Settings</b>."
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")]
    ]))


def register_clone_handlers(client):
    cset.register(client)
    master_manager.register(client)
    single_link.register(client)
    cbatch.register(client, base_group=-1)
    chbatch.register(client, base_group=-3)
    special_link.register(client, base_group=-5)

    # Public clone commands
    command_map = {
        "start": cmd.start,
        "help": clean_help,
        "getlink": single_link.genlink_prompt,
        "link": single_link.genlink_prompt,
        "genlink": single_link.genlink_prompt,
        "universal_link": cmd.universal_link,
        "shortener": cmd.shortener,
        "api": cmd.api_handler,
        "base_site": cmd.base_site_handler,
    }

    advanced_commands = {
        "admin": "admin_panel", "stats": "stats", "broadcast": "broadcast",
        "ban": "ban", "unban": "unban", "force_sub": "force_sub",
        "caption": "caption", "button": "button", "protect": "protect",
        "auto_delete": "auto_delete", "no_forward": "no_forward",
        "moderator": "moderator", "access_token": "access_token",
        "transfer_db": "transfer_db", "deactivate": "deactivate",
        "mode": "mode", "restart": "restart", "delete": "delete",
        "start_msg": "start_msg",
    }

    for command, name in advanced_commands.items():
        fn = getattr(adv, name, None)
        if callable(fn):
            command_map[command] = fn

    for command, handler in command_map.items():
        client.add_handler(MessageHandler(handler, filters.command(command) & filters.private), group=1)

    callback = getattr(cmd, "callbacks", None)
    if callable(callback):
        client.add_handler(CallbackQueryHandler(callback), group=2)

    advanced_callback = getattr(adv, "callbacks", None)
    if callable(advanced_callback) and advanced_callback is not callback:
        client.add_handler(CallbackQueryHandler(advanced_callback), group=2)

    return client
