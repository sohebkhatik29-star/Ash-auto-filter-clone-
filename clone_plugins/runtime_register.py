"""Register handlers on dynamically-created Pyrogram clone clients."""

from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins import advanced as adv
from clone_plugins import clone_settings_ui as cset
from link_modules import register_all_link_modules, single_link, universal_link
from clone_plugins import master_manager


async def clean_help(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open help\n"
        "• /getlink — Create a single shareable file link\n"
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


async def verification_link_handler(client, message):
    """Handle verification /start payload without delivering the file."""
    if len(message.command) != 2:
        return
    data = message.command[1]
    if not (data.startswith("verify_") or data.startswith("verify-")):
        return

    me = client.me or (await client.get_me())
    token_str = data.split("_", 1)[1] if data.startswith("verify_") else data.split("-", 1)[1]
    orig_payload, slot_used = cmd.consume_verify_token(token_str, message.from_user.id, me.id)

    if orig_payload is None and cmd.mongo_db is not None:
        rec_t = cmd.mongo_db.access_tokens.find_one({
            "bot_id": me.id, "token": token_str, "user_id": int(message.from_user.id)
        })
        if rec_t:
            orig_payload = ""
            slot_used = 1

    if orig_payload is None:
        await message.reply("❌ <b>Invalid or expired verification link!</b>\n\nPlease verify again.")
        raise StopPropagation

    rec = cmd.bot_record(client)
    v_key = f"verify_{slot_used}" if slot_used > 1 else "verify_1"
    v_cfg = rec.get(v_key, {})
    time_mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))
    cmd.set_user_verified(message.from_user.id, me.id, duration_minutes=time_mins, slot=slot_used)
    dur_str = cmd.format_time_minutes(time_mins)

    log_ch = rec.get("verify_log_channel")
    if log_ch:
        try:
            import datetime
            now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            await client.send_message(int(log_ch), (
                "🎯 <b>NEW USER VERIFIED</b>\n\n"
                f"👤 <b>User:</b> {message.from_user.mention} (<code>{message.from_user.id}</code>)\n"
                f"⏰ <b>Validity:</b> <code>{dur_str}</code>\n"
                f"🔢 <b>Step:</b> <code>{slot_used}</code>\n"
                f"📅 <b>Date:</b> <code>{now_str}</code>"
            ))
        except Exception:
            pass

    success_text = (
        f"✅ <b>Hey {message.from_user.mention}, you are successfully verified!</b>\n\n"
        f"Now you have unlimited access for all files for <b>{dur_str}</b>."
    )
    if orig_payload:
        await message.reply(success_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 GET YOUR FILE", url=f"https://t.me/{me.username}?start={orig_payload}")]
        ]))
    else:
        await message.reply(success_text)
    raise StopPropagation


async def start_handler(client, message):
    """Use one /start handler so verification cannot race another /start handler."""
    if len(message.command) == 2:
        data = message.command[1]
        if data.startswith("verify_") or data.startswith("verify-"):
            return await verification_link_handler(client, message)
    return await cmd.start(client, message)


def register_clone_handlers(client):
    cset.register(client)
    master_manager.register(client)
    register_all_link_modules(client, is_master=False)

    command_map = {
        "start": start_handler,
        "help": clean_help,
        "clone": cmd.clone_command,
        "getlink": single_link.genlink_prompt,
        "link": single_link.genlink_prompt,
        "genlink": single_link.genlink_prompt,
        "universal_link": universal_link.universal_link_cmd,
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
