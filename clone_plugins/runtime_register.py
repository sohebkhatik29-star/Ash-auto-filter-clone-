"""Register handlers on dynamically-created Pyrogram clone clients."""
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins import advanced as adv
from clone_plugins import clone_settings_ui as cset
from clone_plugins import single_link


async def clean_help(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open this help\n"
        "• /getlink — Create a single shareable file link\n"
        "• /custom_batch — Create custom batch links\n"
        "• /shortener — Shortener settings\n"
        "• /settings — Customize bot\n"
        "• /api KEY — Set shortener API\n"
        "• /base_site SITE — Set shortener site\n"
        "• /clone — Create your own clone\n\n"
        "👑 <b>Owner / Moderator</b>\n"
        "• /admin • /stats • /broadcast\n"
        "• /ban • /unban • /force_sub\n"
        "• /caption • /button • /protect\n"
        "• /auto_delete • /no_forward • /moderator\n"
        "• /access_token • /transfer_db • /deactivate\n"
        "• /mode • /restart • /delete • /start_msg\n\n"
        "⚙️ Owner features are also available from <b>Settings → My Clone Bot</b>."
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")]
    ]))


def register_clone_handlers(client):
    cset.register(client)
    single_link.register(client)

    # Public clone commands: keep only the requested single-link and custom-batch flows.
    command_map = {
        "start": cmd.start,
        "help": clean_help,
        "getlink": single_link.genlink_prompt,
        "custom_batch": cmd.custom_batch,
        "shortener": cmd.shortener,
        "api": cmd.api_handler,
        "base_site": cmd.base_site_handler,
    }

    # Legacy public link/batch commands are intentionally not registered.
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
