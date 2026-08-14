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


def _lock(client, user_id):
    key = (int(client.me.id), int(user_id))
    if key not in _BATCH_LOCKS:
        _BATCH_LOCKS[key] = asyncio.Lock()
    return _BATCH_LOCKS[key]


def _session(client, user_id):
    if mongo_db is None:
        return None
    return mongo_db.custom_batch_sessions.find_one({"bot_id": client.me.id, "user_id": int(user_id), "active": True})


def _controls(session_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 GENERATE LINK", callback_data=f"cb_generate_{session_id}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}")],
    ])


def _text(count):
    if not count:
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


async def _replace_panel(client, session, count):
    """Delete the previous status panel and put exactly one fresh panel below it."""
    old_chat = session.get("control_chat_id")
    old_msg = session.get("control_message_id")
    if old_chat and old_msg:
        try:
            await client.delete_messages(int(old_chat), int(old_msg))
        except Exception:
            pass

    sent = await client.send_message(
        int(session["user_id"]),
        _text(count),
        reply_markup=_controls(session["session_id"]),
    )
    mongo_db.custom_batch_sessions.update_one(
        {"_id": session["_id"], "active": True},
        {"$set": {"control_chat_id": int(sent.chat.id), "control_message_id": int(sent.id)}}
    )
    return sent


async def custom_batch(client, message):
    if not cmd.is_owner_or_mod(client, message.from_user.id) and cmd.bot_record(client).get("mode", "private") == "private":
        return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    async with _lock(client, message.from_user.id):
        # Starting Custom Batch must cancel any stale /getlink or /genlink
        # waiting state, otherwise forwarded files can also trigger the old
        # single-link collector and create extra "HERE IS YOUR LINK" panels.
        try:
            from clone_plugins import single_link
            single_link._PENDING.pop((int(client.me.id), int(message.from_user.id)), None)
        except Exception:
            pass

        mongo_db.custom_batch_sessions.delete_many({"bot_id": client.me.id, "user_id": int(message.from_user.id)})
        session_id = secrets.token_urlsafe(10)
        doc = {
            "session_id": session_id,
            "bot_id": client.me.id,
            "user_id": int(message.from_user.id),
            "messages": [],
            "active": True,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        result = mongo_db.custom_batch_sessions.insert_one(doc)
        session = mongo_db.custom_batch_sessions.find_one({"_id": result.inserted_id})
        await _replace_panel(client, session, 0)
    raise StopPropagation


async def capture_message(client, message):
    if mongo_db is None or not message.from_user or not message.chat:
        return
    if message.chat.type.value != "private":
        return
    if message.text and message.text.startswith("/"):
        return

    async with _lock(client, message.from_user.id):
        session = _session(client, message.from_user.id)
        if not session or not session.get("active"):
            return

        messages = list(session.get("messages", []))
        if len(messages) >= MAX_FILES:
            return

        item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
        if any(x.get("chat_id") == item["chat_id"] and x.get("message_id") == item["message_id"] for x in messages):
            return
        messages.append(item)

        mongo_db.custom_batch_sessions.update_one(
            {"_id": session["_id"], "active": True},
            {"$set": {"messages": messages, "updated_at": int(time.time())}}
        )
        session["messages"] = messages

        await _replace_panel(client, session, len(messages))


async def _generate(client, query, session):
    messages = list(session.get("messages", []))[:MAX_FILES]
    if not messages:
        return await query.answer("Forward or send at least one message first.", show_alert=True)

    links = mongo_db.custom_batch_links
    token = secrets.token_urlsafe(18)
    rec = cmd.bot_record(client)
    protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    links.insert_one({
        "token": token,
        "bot_id": client.me.id,
        "owner_id": int(session["user_id"]),
        "messages": messages,
        "protected": protected,
        "created_at": int(time.time()),
    })

    username = (await client.get_me()).username
    url = f"https://t.me/{username}?start=batch_{token}"
    owner = cmd.owner_id(client) or int(session["user_id"])
    try:
        shown = await get_short_link(await get_user(owner), url)
    except Exception:
        shown = url

    old_chat = session.get("control_chat_id")
    old_msg = session.get("control_message_id")
    if old_chat and old_msg:
        try:
            await client.delete_messages(int(old_chat), int(old_msg))
        except Exception:
            pass

    text = (
        "✅ <b>CUSTOM BATCH LINK GENERATED</b>\n\n"
        f"📦 <b>Messages:</b> {len(messages)}\n\n"
        f"🔗 <b>Link:</b>\n{shown}"
    )
    await client.send_message(int(session["user_id"]), text)
    mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
    await query.answer("Link generated successfully.")


async def callback(client, query):
    data = query.data or ""
    parts = data.split("_", 2)
    if len(parts) != 3 or parts[0] != "cb":
        return
    action, session_id = parts[1], parts[2]
    if mongo_db is None:
        return await query.answer("Database is not configured.", show_alert=True)

    async with _lock(client, query.from_user.id):
        session = mongo_db.custom_batch_sessions.find_one({"session_id": session_id})
        if not session or int(session.get("user_id", 0)) != int(query.from_user.id):
            return await query.answer("This batch session is not yours or has expired.", show_alert=True)
        if action == "generate":
            await _generate(client, query, session)
        elif action == "cancel":
            old_chat = session.get("control_chat_id")
            old_msg = session.get("control_message_id")
            if old_chat and old_msg:
                try:
                    await client.delete_messages(int(old_chat), int(old_msg))
                except Exception:
                    pass
            mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
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
