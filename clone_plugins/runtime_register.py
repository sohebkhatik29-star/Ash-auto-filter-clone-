"""Register handlers on dynamically-created Pyrogram clone clients."""
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from clone_plugins import commands as cmd
from clone_plugins import advanced as adv
from clone_plugins import clone_settings_ui as cset
from clone_plugins import single_link


def register_clone_handlers(client):
    cset.register(client)
    single_link.register(client)

    # Requested public commands: only single-link and custom-batch link flows.
    command_map = {
        "start": cmd.start,
        "help": cmd.help_command,
        "getlink": single_link.genlink_prompt,
        "custom_batch": cmd.custom_batch,
        "shortener": cmd.shortener,
        "api": cmd.api_handler,
        "base_site": cmd.base_site_handler,
    }

    # Removed from the public command menu/handlers:
    # /link, /genlink, /batch, /special_link, /universal_link.
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
