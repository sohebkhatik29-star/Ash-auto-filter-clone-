import asyncio
import secrets
import time

from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins import commands as cmd
from clone_plugins.users_api import get_user, get_short_link
from plugins.clone import mongo_db


CHUNK_SIZE = 100
MAX_FILES = 5000


def _sessions(client):
    return mongo_db.custom_batch_sessions if mongo_db is not None else None


def _links(client):
    return mongo_db.custom_batch_links if mongo_db is not None else None


def _session(client, user_id):
    col = _sessions(client)
    if col is None:
        return None
    return col.find_one({"bot_id": client.me.id, "user_id": int(user_id), "active": True})


def _controls(session_id, paused=False, chunk_ready=False):
    rows = []
    if paused or chunk_ready:
        rows.append([InlineKeyboardButton("▶️ CONTINUE", callback_data=f"cb_continue_{session_id}")])
    else:
        rows.append([InlineKeyboardButton("⏸ PAUSE", callback_data=f"cb_pause_{session_id}")])
    rows.append([InlineKeyboardButton("🔗 GENERATE LINK", callback_data=f"cb_generate_{session_id}")])
    rows.append([InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}")])
    return InlineKeyboardMarkup(rows)


def _text(count, paused=False):
    if count == 0:
        return (
            "📦 <b>CUSTOM BATCH</b>\n\n"
            "Send or forward as many messages as you want.\n"
            "You can select multiple messages in Telegram and forward them together; I will save every supported file automatically.\n\n"
            "When finished, tap 🔗 <b>GENERATE LINK</b>."
        )
    extra = "\n\n📦 <b>%d files collected.</b>" % count
    if count % CHUNK_SIZE == 0:
        extra += "\n\nIf you want to forward more messages, tap ▶️ <b>CONTINUE</b>."
    return (
        "📦 <b>CUSTOM BATCH</b>\n\n"
        "Send or forward as many messages as you want.\n"
        "Multiple forwarded messages are saved automatically."
        + extra
        + "\n\nWhen finished, tap 🔗 <b>GENERATE LINK</b>."
    )


async def custom_batch(client, message):
    if not cmd.is_owner_or_mod(client, message.from_user.id) and cmd.bot_record(client).get("mode", "private") == "private":
        return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    mongo_db.custom_batch_sessions.delete_many({"bot_id": client.me.id, "user_id": int(message.from_user.id)})
    session_id = secrets.token_urlsafe(10)
    doc = {
        "session_id": session_id,
        "bot_id": client.me.id,
        "user_id": int(message.from_user.id),
        "file_ids": [],
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


async def capture_media(client, message):
    if mongo_db is None or not message.from_user:
        return
    session = _session(client, message.from_user.id)
    if not session or not session.get("active") or session.get("paused"):
        return
    if not message.media:
        return

    media = getattr(message, message.media.value, None)
    file_id = getattr(media, "file_id", None)
    if not file_id:
        return

    files = list(session.get("file_ids", []))
    if len(files) >= MAX_FILES:
        try:
            await client.send_message(message.chat.id, f"⚠️ Maximum {MAX_FILES} files reached. Tap 🔗 GENERATE LINK.")
        except Exception:
            pass
        return
    files.append(file_id)
    now = int(time.time())
    mongo_db.custom_batch_sessions.update_one(
        {"_id": session["_id"]},
        {"$set": {"file_ids": files, "updated_at": now}},
    )

    if len(files) % CHUNK_SIZE == 0:
        try:
            await client.edit_message_text(
                message.chat.id,
                session.get("control_message_id"),
                _text(len(files)),
                reply_markup=_controls(session["session_id"], chunk_ready=True),
            )
        except Exception:
            pass


async def _generate(client, query, session):
    files = list(session.get("file_ids", []))[:MAX_FILES]
    if not files:
        return await query.answer("Send or forward at least one file first.", show_alert=True)

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
        "file_ids": files,
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
        f"📦 <b>Files:</b> {len(files)}\n\n"
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

    if action == "continue":
        mongo_db.custom_batch_sessions.update_one({"_id": session["_id"]}, {"$set": {"paused": False, "active": True}})
        count = len(session.get("file_ids", []))
        await query.message.edit_text(_text(count), reply_markup=_controls(session_id, paused=False))
        await query.answer("You can forward more messages now.")
    elif action == "pause":
        mongo_db.custom_batch_sessions.update_one({"_id": session["_id"]}, {"$set": {"paused": True, "active": True}})
        count = len(session.get("file_ids", []))
        await query.message.edit_text(_text(count, paused=True), reply_markup=_controls(session_id, paused=True))
        await query.answer("Batch collection paused.")
    elif action == "generate":
        await _generate(client, query, session)
    elif action == "cancel":
        mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
        await query.message.edit_text("❌ <b>Custom batch cancelled.</b>")
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

    files = list(record.get("file_ids", []))
    if not files:
        await message.reply("❌ This batch contains no files.")
        raise StopPropagation

    await message.reply(f"📦 <b>Sending {len(files)} files...</b>")
    for file_id in files:
        try:
            await cmd.deliver_file(client, message.from_user.id, file_id, protected=bool(record.get("protected", False)))
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await message.reply("✅ <b>Batch delivery completed.</b>")
    raise StopPropagation


def register(client, base_group=-1):
    private = filters.private
    client.add_handler(MessageHandler(batch_start, filters.command("start") & private), group=base_group)
    client.add_handler(MessageHandler(custom_batch, filters.command("custom_batch") & private), group=base_group)
    client.add_handler(MessageHandler(capture_media, private & filters.media), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(callback, filters.regex(r"^cb_(continue|pause|generate|cancel)_[A-Za-z0-9_-]+$")), group=base_group)
    return client
