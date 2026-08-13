"""Shareable link generators for clone bots.

/genlink is intentionally interactive: after the command, the next message or
file sent/forwarded to the bot becomes the single link target.
"""
import base64
import secrets
import time

from pyrogram import Client, filters, StopPropagation, enums
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


async def interactive_genlink(client, message):
    _PENDING[(client.me.id, message.from_user.id)] = int(time.time())
    await message.reply(
        "📩 <b>Send a message or file now.</b>\n\n"
        "You can send or forward it directly here.\n"
        "I will create a shareable link for that single message/file.\n\n"
        "/cancel - cancel"
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
        await message.reply("❌ Single-link mode is waiting for a message or file. Use /cancel first if you want to stop.")
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
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 SHARE URL", url=link)]])

    await message.reply(
        "⭕ <b>HERE IS YOUR LINK:</b>\n\n"
        f"🔗 <b>ORIGINAL LINK:</b> {original}\n\n"
        f"🔗 <b>SHARE LINK:</b> {link}",
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

    try:
        from clone_plugins.commands import access_verification, force_markup
        access = await access_verification(client, message.from_user.id, message.command[1])
        if access:
            await message.reply("<b>🔐 Please verify first to access this file.</b>", reply_markup=access)
            raise StopPropagation
        force = await force_markup(client, message.from_user.id, message.command[1])
        if force:
            await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=force)
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
        await message.reply("❌ Unable to deliver this message. The original message may no longer be available.")
    raise StopPropagation


async def legacy_batch(client, message):
    replied = message.reply_to_message
    if not replied:
        return await message.reply("Reply to the first file and use <code>/batch N</code>.")
    try:
        count = int(message.command[1]) if len(message.command) > 1 else 1
        if not 1 <= count <= 20:
            raise ValueError
    except ValueError:
        return await message.reply("Usage: <code>/batch 5</code> (1-20 files)")

    username = (await client.get_me()).username
    links = []
    for msg_id in range(replied.id, replied.id + count):
        try:
            msg = await client.get_messages(replied.chat.id, msg_id)
            if not msg or msg.empty or not msg.media:
                continue
            media = getattr(msg, msg.media.value, None)
            file_id = getattr(media, "file_id", None)
            if not file_id:
                continue
            payload = base64.urlsafe_b64encode(("file_" + file_id).encode()).decode().rstrip("=")
            links.append(f"https://t.me/{username}?start={payload}")
        except Exception:
            continue
    if not links:
        return await message.reply("❌ No supported files were found in that range.")
    await message.reply("📦 <b>Batch Links</b>\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(links, 1)))


def register(client):
    private = filters.private
    client.add_handler(MessageHandler(interactive_genlink, filters.command("genlink") & private), group=-10)
    client.add_handler(MessageHandler(capture_interactive, private), group=-9)
    client.add_handler(MessageHandler(open_interactive, filters.command("start") & private), group=-8)
    return client


@Client.on_message(filters.command("genlink") & filters.private)
async def genlink_fallback(client, message):
    await interactive_genlink(client, message)


@Client.on_message(filters.command("batch") & filters.private)
async def batch_link(client, message):
    await legacy_batch(client, message)
