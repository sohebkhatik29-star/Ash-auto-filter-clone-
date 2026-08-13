"""Interactive multi-message batch collector.

/custom_batch starts a collector. The user can select and forward many messages
in one Telegram action (or send them one after another). Each incoming message
is stored automatically. Generate Link creates one shareable batch URL.
"""
import base64
import secrets
import time

from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from plugins.clone import mongo_db
from clone_plugins.commands import bot_record, is_owner_or_mod, force_markup, access_verification
from clone_plugins.users_api import get_user, get_short_link

_SESSIONS = {}
MAX_MESSAGES = 200


def _key(client, user_id):
    return (int(client.me.id), int(user_id))


def _markup(paused=False):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ RESUME" if paused else "⏸ PAUSE", callback_data="mb_pause")],
        [InlineKeyboardButton("🔗 GENERATE LINK", callback_data="mb_generate")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="mb_cancel")],
    ])


async def start_custom_batch(client, message):
    if not is_owner_or_mod(client, message.from_user.id) and bot_record(client).get("mode", "private") == "private":
        await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
        raise StopPropagation
    _SESSIONS[_key(client, message.from_user.id)] = {
        "items": [],
        "paused": False,
        "created_at": int(time.time()),
    }
    await message.reply(
        "📦 <b>CUSTOM BATCH</b>\n\n"
        "Send or forward <b>as many messages as you want</b>.\n"
        "You can select multiple messages in Telegram and forward them together; "
        "I will save every message automatically.\n\n"
        "When finished, tap <b>🔗 GENERATE LINK</b>.",
        reply_markup=_markup(),
    )
    raise StopPropagation


async def collect_message(client, message):
    key = _key(client, message.from_user.id)
    session = _SESSIONS.get(key)
    if not session or session.get("paused"):
        return
    if message.text and message.text.startswith("/"):
        return
    if len(session["items"]) >= MAX_MESSAGES:
        await message.reply(f"⚠️ Maximum {MAX_MESSAGES} messages reached. Tap GENERATE LINK.")
        session["paused"] = True
        raise StopPropagation
    item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
    if item not in session["items"]:
        session["items"].append(item)
    count = len(session["items"])
    try:
        await message.reply(
            f"✅ <b>Stored Messages:</b> {count}\n\n"
            "Send/forward more messages, or tap <b>🔗 GENERATE LINK</b>.",
            reply_markup=_markup(),
        )
    except Exception:
        pass
    raise StopPropagation


async def batch_callback(client, query):
    key = _key(client, query.from_user.id)
    session = _SESSIONS.get(key)
    if not session:
        await query.answer("No active batch. Use /custom_batch first.", show_alert=True)
        return
    data = query.data
    if data == "mb_cancel":
        _SESSIONS.pop(key, None)
        await query.answer("Batch cancelled.")
        try:
            await query.message.edit_text("❌ <b>Batch cancelled.</b>")
        except Exception:
            pass
        return
    if data == "mb_pause":
        session["paused"] = not session.get("paused", False)
        await query.answer("Paused." if session["paused"] else "Resumed.")
        try:
            await query.message.edit_reply_markup(_markup(session["paused"]))
        except Exception:
            pass
        return
    if data != "mb_generate":
        return
    if not session["items"]:
        await query.answer("Send at least one message first.", show_alert=True)
        return
    if mongo_db is None:
        await query.answer("Database is not configured.", show_alert=True)
        return

    token = secrets.token_urlsafe(18)
    mongo_db.share_links.update_one(
        {"bot_id": client.me.id, "token": token},
        {"$set": {
            "bot_id": client.me.id,
            "token": token,
            "kind": "batch",
            "messages": session["items"],
            "owner_id": int(query.from_user.id),
            "created_at": int(time.time()),
        }},
        upsert=True,
    )
    payload = base64.urlsafe_b64encode(f"batch_{token}".encode()).decode().rstrip("=")
    username = (await client.get_me()).username
    original = f"https://t.me/{username}?start={payload}"
    owner = int(bot_record(client).get("user_id", 0)) or int(query.from_user.id)
    short = await get_short_link(await get_user(owner), original)
    link = short or original
    _SESSIONS.pop(key, None)
    await query.answer("Batch link generated.")
    await query.message.edit_text(
        f"✅ <b>BATCH LINK READY</b>\n\n🔗 {link}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 SHARE URL", url=link)]]),
    )


async def open_batch(client, message):
    if len(message.command) != 2 or mongo_db is None:
        return
    data = message.command[1]
    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, token = decoded.split("_", 1)
    except Exception:
        return
    if prefix != "batch" or not token:
        return
    record = mongo_db.share_links.find_one({"bot_id": client.me.id, "token": token, "kind": "batch"})
    if not record:
        await message.reply("❌ This batch link is invalid or expired.")
        raise StopPropagation

    access = await access_verification(client, message.from_user.id, data)
    if access:
        await message.reply("<b>🔐 Please verify first to access this batch.</b>", reply_markup=access)
        raise StopPropagation
    force = await force_markup(client, message.from_user.id, data)
    if force:
        await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=force)
        raise StopPropagation

    delivered = 0
    for item in record.get("messages", []):
        try:
            await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=int(item["chat_id"]),
                message_id=int(item["message_id"]),
            )
            delivered += 1
        except Exception:
            continue
    if not delivered:
        await message.reply("❌ Unable to deliver the stored messages.")
    raise StopPropagation


def register(client):
    private = filters.private
    client.add_handler(MessageHandler(start_custom_batch, filters.command("custom_batch") & private), group=-30)
    client.add_handler(MessageHandler(open_batch, filters.command("start") & private), group=-31)
    client.add_handler(MessageHandler(collect_message, private), group=-29)
    client.add_handler(CallbackQueryHandler(batch_callback, filters.regex(r"^mb_(pause|generate|cancel)$")), group=-30)
    return client
