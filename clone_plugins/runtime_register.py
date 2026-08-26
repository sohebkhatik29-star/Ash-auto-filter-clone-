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
    """Handle verify_<token> before the normal /start handler.

    A successful verification only unlocks the next step and shows GET YOUR FILE.
    It deliberately does not call cmd.start(), so the file cannot be delivered
    before the user presses GET YOUR FILE.  The normal /start handler then checks
    the next verification slot (if any) or delivers the file after all slots pass.
    """
    if len(message.command) != 2:
        return

    data = message.command[1]
    if not (data.startswith("verify_") or data.startswith("verify-")):
        return

    me = client.me or (await client.get_me())
    token_str = data.split("_", 1)[1] if data.startswith("verify_") else data.split("-", 1)[1]

    orig_payload, slot_used = cmd.consume_verify_token(
        token_str, message.from_user.id, me.id
    )

    # Keep the same legacy access-token fallback used by the existing flow.
    if orig_payload is None and cmd.mongo_db is not None:
        rec_t = cmd.mongo_db.access_tokens.find_one({
            "bot_id": me.id,
            "token": token_str,
            "user_id": int(message.from_user.id),
        })
        if rec_t:
            orig_payload = ""
            slot_used = 1

    if orig_payload is None:
        await message.reply(
            "❌ <b>Invalid or expired verification link!</b>\n\n"
            "Please verify again."
        )
        raise StopPropagation

    rec = cmd.bot_record(client)
    v_key = f"verify_{slot_used}" if slot_used > 1 else "verify_1"
    v_cfg = rec.get(v_key, {})
    time_mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))

    cmd.set_user_verified(
        message.from_user.id,
        me.id,
        duration_minutes=time_mins,
        slot=slot_used,
    )

    dur_str = cmd.format_time_minutes(time_mins)

    # Preserve verification logging.
    log_ch = rec.get("verify_log_channel")
    if log_ch:
        try:
            import datetime
            now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            log_text = (
                "🎯 <b>NEW USER VERIFIED</b>\n\n"
                f"👤 <b>User:</b> {message.from_user.mention} "
                f"(<code>{message.from_user.id}</code>)\n"
                f"⏰ <b>Validity:</b> <code>{dur_str}</code>\n"
                f"🔢 <b>Step:</b> <code>{slot_used}</code>\n"
                f"📅 <b>Date:</b> <code>{now_str}</code>"
            )
            await client.send_message(int(log_ch), log_text)
        except Exception:
            pass

    success_text = (
        f"✅ <b>Hey {message.from_user.mention}, you are successfully verified!</b>\n\n"
        f"Now you have unlimited access for all files for <b>{dur_str}</b>."
    )

    # Never auto-open the original payload here.  The only next action is the
    # explicit GET YOUR FILE button, which routes through the normal /start
    # access-verification logic and therefore handles additional slots too.
    if orig_payload:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📥 GET YOUR FILE",
                url=f"https://t.me/{me.username}?start={orig_payload}"
            )]
        ])
        await message.reply(success_text, reply_markup=markup)
    else:
        await message.reply(success_text)

    raise StopPropagation


def register_clone_handlers(client):
    cset.register(client)
    master_manager.register(client)
    register_all_link_modules(client, is_master=False)

    # Verification links must be consumed before the normal /start handler.
    # Group 0 + StopPropagation prevents the old handler from auto-delivering
    # the file immediately after verification.
    client.add_handler(
        MessageHandler(
            verification_link_handler,
            filters.command("start") & filters.private
        ),
        group=0,
    )

    # Public clone commands
    command_map = {
        "start": cmd.start,
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
