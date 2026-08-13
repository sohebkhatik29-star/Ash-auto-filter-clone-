"""Single-message/file shareable link flow for ASH clones."""
import base64
import secrets
import time

from pyrogram import StopPropagation, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins.users_api import get_user, get_short_link
from plugins.clone import mongo_db
from clone_plugins.commands import bot_record, force_markup, access_verification

_PENDING = {}


def _payload(token: str) -> str:
    return base64.urlsafe_b64encode(f"msg_{token}".encode()).decode().rstrip("=")


def _decode(payload: str):
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("ascii")
        prefix, token = raw.split("_", 1)
        if prefix == "msg" and token:
            return token
    except Exception:
        pass
    return None


async def genlink_prompt(client, message):
    _PENDING[(client.me.id, message.from_user.id)] = int(time.time())
    await message.reply(
        "📩 <b>Send or forward the message/file now.</b>\n\n"
        "No reply command is needed. I will automatically create the single shareable link.\n\n"
        "/cancel - cancel"
    )
    raise StopPropagation


async def capture_single(client, message):
    key = (client.me.id, message.from_user.id)
    if key not in _PENDING:
        return
    _PENDING.pop(key, None)
    if message.text and message.text.strip().lower() == "/cancel":
        await message.reply("❌ Cancelled.")
        raise StopPropagation
    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation
    token = secrets.token_urlsafe(18)
    mongo_db.share_links.update_one(
        {"bot_id": client.me.id, "token": token},
        {"$set": {"bot_id": client.me.id, "token": token, "source_chat_id": int(message.chat.id), "source_message_id": int(message.id), "owner_id": int(message.from_user.id), "created_at": int(time.time())}},
        upsert=True,
    )
    username = (await client.get_me()).username
    original = f"https://t.me/{username}?start={_payload(token)}"
    owner = int(bot_record(client).get("user_id", 0)) or message.from_user.id
    short = await get_short_link(await get_user(owner), original)
    link = short or original
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 SHARE URL", url=link)]])
    await message.reply(
        "✅ <b>HERE IS YOUR LINK:</b>\n\n"
        f"🔗 <b>LINK:</b> {link}",
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    raise StopPropagation


async def open_single(client, message):
    if len(message.command) != 2:
        return
    token = _decode(message.command[1])
    if not token or mongo_db is None:
        return
    record = mongo_db.share_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        await message.reply("❌ This link is invalid or expired.")
        raise StopPropagation
    payload = message.command[1]
    access = await access_verification(client, message.from_user.id, payload)
    if access:
        await message.reply("<b>🔐 Please verify first to access this file.</b>", reply_markup=access)
        raise StopPropagation
    force = await force_markup(client, message.from_user.id, payload)
    if force:
        await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=force)
        raise StopPropagation
    try:
        await client.copy_message(chat_id=message.from_user.id, from_chat_id=int(record["source_chat_id"]), message_id=int(record["source_message_id"]))
    except Exception:
        await message.reply("❌ Unable to deliver this message. The original message may no longer be available.")
    raise StopPropagation


def register(client):
    private = filters.private
    client.add_handler(MessageHandler(genlink_prompt, filters.command(["genlink", "getlink"]) & private), group=-100)
    client.add_handler(MessageHandler(capture_single, private), group=-99)
    client.add_handler(MessageHandler(open_single, filters.command("start") & private), group=-98)
    # Also register the interactive multi-message collector. This keeps the
    # clone runtime compatible without needing a second registration module.
    from clone_plugins import multi_batch
    multi_batch.register(client)
    return client
