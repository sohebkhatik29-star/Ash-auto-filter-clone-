"""Single-message share link generator for clone bots.

/getlink starts an interactive flow: send/forward one message or file directly
and the bot creates exactly one shareable link.
"""
import base64
import secrets
import time

from pyrogram import Client, filters, StopPropagation
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins.users_api import get_user, get_short_link

_PENDING = {}


def _encode(token):
    return base64.urlsafe_b64encode(f"msg_{token}".encode()).decode().rstrip("=")


def _decode(payload):
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        prefix, token = raw.split("_", 1)
        return token if prefix == "msg" and token else None
    except Exception:
        return None


def _db():
    from plugins.clone import mongo_db
    return mongo_db


def _bot_owner(client, fallback):
    try:
        db = _db()
        if db is not None:
            row = db.bots.find_one({"bot_id": client.me.id}) or {}
            return int(row.get("user_id", 0)) or fallback
    except Exception:
        pass
    return fallback


async def interactive_getlink(client, message):
    _PENDING[(client.me.id, message.from_user.id)] = int(time.time())
    await message.reply(
        "📩 <b>Send or forward the message/file now.</b>\n\n"
        "I will create one shareable link automatically.\n\n"
        "/cancel - cancel"
    )
    raise StopPropagation


async def disabled_old_link_commands(client, message):
    await message.reply("❌ This command is disabled. Use /getlink.")
    raise StopPropagation


async def clean_help(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open this help\n"
        "• /getlink — Create a single shareable link\n"
        "• /batch N — Create batch links\n"
        "• /custom_batch N — Custom batch links\n"
        "• /special_link — Special link\n"
        "• /universal_link — Universal link\n"
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
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")]
        ]),
    )
    raise StopPropagation


async def capture_interactive(client, message):
    key = (client.me.id, message.from_user.id)
    if key not in _PENDING:
        return
    _PENDING.pop(key, None)

    if message.text and message.text.strip().lower() == "/cancel":
        await message.reply("❌ Cancelled.")
        raise StopPropagation
    if message.text and message.text.startswith("/"):
        await message.reply("❌ Send/forward the message or file, or use /cancel.")
        _PENDING[key] = int(time.time())
        raise StopPropagation

    db = _db()
    if db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    token = secrets.token_urlsafe(18)
    db.share_links.update_one(
        {"bot_id": client.me.id, "token": token},
        {"$set": {
            "bot_id": client.me.id,
            "token": token,
            "source_chat_id": int(message.chat.id),
            "source_message_id": int(message.id),
            "owner_id": int(message.from_user.id),
            "created_at": int(time.time()),
        }},
        upsert=True,
    )

    username = (await client.get_me()).username
    original = f"https://t.me/{username}?start={_encode(token)}"
    owner = _bot_owner(client, message.from_user.id)
    short = await get_short_link(await get_user(owner), original)
    link = short or original

    # Only one link is shown. No duplicate Original/Share Link block.
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 SHARE URL", url=link)]
    ])

    await message.reply(
        "✅ <b>HERE IS YOUR LINK:</b>\n\n"
        f"🔗 <b>LINK:</b> {link}",
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    raise StopPropagation


async def open_interactive(client, message):
    if len(message.command) != 2:
        return
    token = _decode(message.command[1])
    if not token:
        return
    db = _db()
    if db is None:
        return
    record = db.share_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        await message.reply("❌ This link is invalid or expired.")
        raise StopPropagation

    # Use the existing access-token system, but replace its shortener URL
    # with a direct Telegram verification URL so the button opens reliably.
    try:
        from clone_plugins.commands import access_verification, force_markup
        access = await access_verification(client, message.from_user.id, message.command[1])
        if access:
            valid = db.access_tokens.find_one({
                "bot_id": client.me.id,
                "user_id": int(message.from_user.id),
                "payload": message.command[1],
                "expires_at": {"$gt": int(time.time())},
            })
            if valid:
                verify_payload = base64.urlsafe_b64encode(
                    f"verify_{valid['token']}".encode()
                ).decode().rstrip("=")
                username = (await client.get_me()).username
                verify_url = f"https://t.me/{username}?start={verify_payload}"
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 VERIFY & CONTINUE", url=verify_url)]
                ])
                await message.reply(
                    "<b>🔐 Please verify first to access this file.</b>",
                    reply_markup=markup,
                )
                raise StopPropagation
        force = await force_markup(client, message.from_user.id, message.command[1])
        if force:
            await message.reply(
                "<b>🔐 Please join the required channel(s) first.</b>",
                reply_markup=force,
            )
            raise StopPropagation
    except StopPropagation:
        raise
    except Exception:
        pass

    try:
        await client.copy_message(
            chat_id=message.from_user.id,
            from_chat_id=int(record["source_chat_id"]),
            message_id=int(record["source_message_id"]),
        )
    except Exception:
        await message.reply(
            "❌ Unable to deliver this message. The original message may no longer be available."
        )
    raise StopPropagation


def register(client):
    private = filters.private
    # New command: only /getlink.
    client.add_handler(
        MessageHandler(interactive_getlink, filters.command("getlink") & private),
        group=-20,
    )
    # Clean help before the legacy help handler runs.
    client.add_handler(
        MessageHandler(clean_help, filters.command("help") & private),
        group=-22,
    )
    # Stop the old link commands from reaching the legacy handler.
    client.add_handler(
        MessageHandler(
            disabled_old_link_commands,
            filters.command(["link", "genlink"]) & private,
        ),
        group=-21,
    )
    client.add_handler(MessageHandler(capture_interactive, private), group=-19)
    client.add_handler(
        MessageHandler(open_interactive, filters.command("start") & private),
        group=-18,
    )
    return client


@Client.on_message(filters.command("getlink") & filters.private)
async def getlink_fallback(client, message):
    await interactive_getlink(client, message)
