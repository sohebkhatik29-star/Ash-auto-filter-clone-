import asyncio
import secrets
import time

from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins import commands as cmd
from clone_plugins.users_api import get_user, get_short_link
from plugins.clone import mongo_db

MAX_FILES = 5000
_BATCH_LOCKS = {}


def _sessions(client):
    return mongo_db.custom_batch_sessions if mongo_db is not None else None


def _links(client):
    return mongo_db.custom_batch_links if mongo_db is not None else None


def _lock_key(client, user_id):
    return (int(client.me.id), int(user_id))


def _get_lock(client, user_id):
    key = _lock_key(client, user_id)
    lock = _BATCH_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _BATCH_LOCKS[key] = lock
    return lock


def _session(client, user_id):
    col = _sessions(client)
    if col is None:
        return None
    return col.find_one({"bot_id": client.me.id, "user_id": int(user_id), "active": True})


def _controls(session_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 GENERATE LINK", callback_data=f"cb_generate_{session_id}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}")],
    ])


def _text(count):
    if count == 0:
        return (
            "📦 <b>CUSTOM BATCH</b>\n\n"
            "Send or forward as many messages as you want.\n"
            "You can select multiple Telegram messages and forward them together; "
            "I will save every message automatically.\n\n"
            "When finished, tap 🔗 <b>GENERATE LINK</b>."
        )
    return (
        "📦 <b>CUSTOM BATCH</b>\n\n"
        f"📥 <b>Stored Messages: {count}</b>\n\n"
        "Send/forward more messages, or tap 🔗 <b>GENERATE LINK</b>."
    )


async def _replace_control(client, session, count):
    """Keep exactly one visible control panel.

    Some Telegram clients/forwarded-message updates can make an edit silently
    fail. To guarantee one visible panel, remove the old panel first and create
    one replacement, then atomically store its message id in the session.
    """
    chat_id = int(session.get("control_chat_id") or 0)
    old_id = int(session.get("control_message_id") or 0)
    if not chat_id:
        return

    if old_id:
        try:
            await client.delete_messages(chat_id, old_id)
        except Exception:
            pass

    try:
        sent = await client.send_message(
            chat_id,
            _text(count),
            reply_markup=_controls(session["session_id"]),
        )
    except Exception:
        return

    mongo_db.custom_batch_sessions.update_one(
        {"_id": session["_id"], "active": True},
        {"$set": {
            "control_chat_id": int(sent.chat.id),
            "control_message_id": int(sent.id),
            "updated_at": int(time.time()),
        }},
    )


async def custom_batch(client, message):
    if not cmd.is_owner_or_mod(client, message.from_user.id) and cmd.bot_record(client).get("mode", "private") == "private":
        return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    lock = _get_lock(client, message.from_user.id)
    async with lock:
        mongo_db.custom_batch_sessions.delete_many({
            "bot_id": client.me.id,
            "user_id": int(message.from_user.id),
        })
        session_id = secrets.token_urlsafe(10)
        doc = {
            "session_id": session_id,
            "bot_id": client.me.id,
            "user_id": int(message.from_user.id),
            "messages": [],
            "active": True,
            "paused": False,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        mongo_db.custom_batch_sessions.insert_one(doc)
        sent = await message.reply(_text(0), reply_markup=_controls(session_id))
        mongo_db.custom_batch_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"control_chat_id": sent.chat.id, "control_message_id": sent.id}},
        )
    raise StopPropagation


async def capture_message(client, message):
    """Collect private messages and keep only ONE status/control panel visible."""
    if mongo_db is None or not message.from_user:
        return
    if not message.chat or message.chat.type.value != "private":
        return
    if message.text and message.text.startswith("/"):
        return

    lock = _get_lock(client, message.from_user.id)
    async with lock:
        session = _session(client, message.from_user.id)
        if not session or not session.get("active") or session.get("paused"):
            return

        messages = list(session.get("messages", []))
        if len(messages) >= MAX_FILES:
            return

        item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
        if any(x.get("chat_id") == item["chat_id"] and x.get("message_id") == item["message_id"] for x in messages):
            return
        messages.append(item)

        now = int(time.time())
        mongo_db.custom_batch_sessions.update_one(
            {"_id": session["_id"], "active": True},
            {"$set": {"messages": messages, "updated_at": now}},
        )
        session["messages"] = messages
        await _replace_control(client, session, len(messages))


async def _generate(client, query, session):
    messages = list(session.get("messages", []))[:MAX_FILES]
    if not messages:
        return await query.answer("Forward or send at least one message first.", show_alert=True)

    username = (await client.get_me()).username
    token = secrets.token_urlsafe(18)
    rec = cmd.bot_record(client)
    protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    links = _links(client)
    if links is None:
        return await query.answer("Database is not configured.", show_alert=True)

    links.insert_one({
        "token": token,
        "bot_id": client.me.id,
        "owner_id": int(session["user_id"]),
        "messages": messages,
        "protected": protected,
        "created_at": int(time.time()),
    })
    payload = f"batch_{token}"
    url = f"https://t.me/{username}?start={payload}"
    owner = cmd.owner_id(client) or int(session["user_id"])
    try:
        short = await get_short_link(await get_user(owner), url)
    except Exception:
        short = url

    mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
    shown = short if short != url else url
    text = (
        "✅ <b>CUSTOM BATCH LINK GENERATED</b>\n\n"
        f"📦 <b>Messages:</b> {len(messages)}\n\n"
        f"🔗 <b>Link:</b>\n{shown}"
    )
    try:
        await query.message.edit_text(text)
    except Exception:
        await query.message.reply(text)
    await query.answer("Link generated successfully.")


async def callback(client, query):
    data = query.data or ""
    parts = data.split("_", 2)
    if len(parts) != 3 or parts[0] != "cb":
        return
    action, session_id = parts[1], parts[2]
    if mongo_db is None:
        return await query.answer("Database is not configured.", show_alert=True)
    session = mongo_db.custom_batch_sessions.find_one({"session_id": session_id})
    if not session or int(session.get("user_id", 0)) != int(query.from_user.id):
        return await query.answer("This batch session is not yours or has expired.", show_alert=True)

    lock = _get_lock(client, query.from_user.id)
    async with lock:
        session = mongo_db.custom_batch_sessions.find_one({"session_id": session_id})
        if not session:
            return await query.answer("This batch session has expired.", show_alert=True)
        if action == "generate":
            await _generate(client, query, session)
        elif action == "cancel":
            mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
            try:
                await query.message.edit_text("❌ <b>Custom batch cancelled.</b>")
            except Exception:
                pass
            await query.answer("Cancelled.")
    raise StopPropagation


async def batch_start(client, message):
    if len(message.command) != 2 or not message.command[1].startswith("batch_"):
        return
    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation
    token = message.command[1][6:]
    record = mongo_db.custom_batch_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        await message.reply("❌ Invalid or expired batch link.")
        raise StopPropagation

    payload = message.command[1]
    access = await cmd.access_verification(client, message.from_user.id, payload)
    if access:
        await message.reply("<b>🔐 Please verify first to access this batch.</b>", reply_markup=access)
        raise StopPropagation
    force = await cmd.force_markup(client, message.from_user.id, payload)
    if force:
        await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=force)
        raise StopPropagation

    messages = list(record.get("messages", []))
    if not messages:
        old_files = list(record.get("file_ids", []))
        if old_files:
            await message.reply(f"📦 <b>Sending {len(old_files)} files...</b>")
            for file_id in old_files:
                try:
                    await cmd.deliver_file(client, message.from_user.id, file_id, protected=bool(record.get("protected", False)))
                    await asyncio.sleep(0.05)
                except Exception:
                    continue
            await message.reply("✅ <b>Batch delivery completed.</b>")
        else:
            await message.reply("❌ This batch contains no messages.")
        raise StopPropagation

    await message.reply(f"📦 <b>Sending {len(messages)} messages...</b>")
    for item in messages:
        try:
            await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=int(item["chat_id"]),
                message_id=int(item["message_id"]),
                protect_content=bool(record.get("protected", False)),
            )
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await message.reply("✅ <b>Batch delivery completed.</b>")
    raise StopPropagation


def register(client, base_group=-1):
    private = filters.private
    client.add_handler(MessageHandler(batch_start, filters.command("start") & private), group=base_group)
    client.add_handler(MessageHandler(custom_batch, filters.command("custom_batch") & private), group=base_group)
    client.add_handler(MessageHandler(capture_message, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(callback, filters.regex(r"^cb_(generate|cancel)_[A-Za-z0-9_-]+$")), group=base_group)
    return client
