"""Register handlers on dynamically-created Pyrogram clone clients."""
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from clone_plugins import commands as cmd
from clone_plugins import advanced as adv
from clone_plugins import clone_settings_ui as cset
from clone_plugins import single_link


def register_clone_handlers(client):
    # Clone-owner settings first.
    cset.register(client)

    # IMPORTANT: /genlink and its next-message/file flow are owned entirely by
    # single_link. Do not also register cmd.genlink below, otherwise the old
    # reply-to-file implementation can answer /genlink.
    single_link.register(client)

    command_map = {
        "start": cmd.start,
        "help": cmd.help_command,
        # /link keeps the legacy reply-to-file behaviour for compatibility.
        "link": cmd.genlink,
        # /genlink is intentionally NOT here; single_link.register() owns it.
        "batch": cmd.batch,
        "custom_batch": cmd.custom_batch,
        "special_link": cmd.special_link,
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
