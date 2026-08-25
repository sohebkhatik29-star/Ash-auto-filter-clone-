"""Custom Batch link generator and delivery handler.
Main command: /custom_batch
"""
import asyncio
import secrets
import time
import base64
from pyrogram import filters, StopPropagation, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins.users_api import get_user, get_short_link, format_caption
from plugins.clone import mongo_db

MAX_FILES = 5000
_BATCH_LOCKS = {}
_INDEX_TASKS = {}
_LAST_MSG_TIME = {}


def _lock(client, user_id):
    key = (int(client.me.id), int(user_id))
    if key not in _BATCH_LOCKS:
        _BATCH_LOCKS[key] = asyncio.Lock()
    return _BATCH_LOCKS[key]


def _session(client, user_id):
    if mongo_db is None:
        return None
    return mongo_db.custom_batch_sessions.find_one({"bot_id": client.me.id, "user_id": int(user_id), "active": True})


def _controls_initial(session_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 GENERATE LINK", callback_data=f"cb_generate_{session_id}")],
        [InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}")],
    ])


def _controls_indexing(session_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}")],
    ])


def _controls_indexed(session_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CONTINUE", callback_data=f"cb_continue_{session_id}"),
            InlineKeyboardButton("🔗 GENERATE LINK", callback_data=f"cb_generate_{session_id}"),
        ],
        [
            InlineKeyboardButton("❌ CANCEL", callback_data=f"cb_cancel_{session_id}"),
        ],
    ])


def _text_initial(count=0):
    if not count:
        return (
            "📦 <b>CUSTOM BATCH</b>\n\n"
            "Send or forward as many messages as you want.\n"
            "You can select multiple Telegram messages (e.g. 100+) and forward them together.\n"
            "I will index and save every message automatically.\n\n"
            "When finished, tap 🔗 <b>GENERATE LINK</b>."
        )
    return (
        "📦 <b>CUSTOM BATCH (ACTIVE)</b>\n\n"
        f"📥 <b>Stored Files: {count}</b>\n\n"
        "Send or forward more files now. They will be added to this batch.\n"
        "When finished, tap 🔗 <b>GENERATE LINK</b>."
    )


def _text_indexing():
    return (
        "⏳ <b>Index your file...</b>\n\n"
        "📥 Processing incoming messages, please wait..."
    )


def _text_indexed(count):
    return (
        "✅ <b>Your files have been indexed!</b>\n\n"
        f"📦 <b>Total Files: {count}</b>\n\n"
        "Tap <b>CONTINUE</b> to add more files, or <b>GENERATE LINK</b> to create your shareable link."
    )


async def _replace_panel(client, session, text, reply_markup):
    """Delete the previous status panel and put exactly one fresh panel below it."""
    old_chat = session.get("control_chat_id")
    old_msg = session.get("control_message_id")
    if old_chat and old_msg:
        try:
            await client.delete_messages(int(old_chat), int(old_msg))
        except Exception:
            pass
    try:
        sent = await client.send_message(
            int(session["user_id"]),
            text,
            reply_markup=reply_markup,
        )
        mongo_db.custom_batch_sessions.update_one(
            {"_id": session["_id"], "active": True},
            {"$set": {"control_chat_id": int(sent.chat.id), "control_message_id": int(sent.id)}}
        )
        session["control_chat_id"] = int(sent.chat.id)
        session["control_message_id"] = int(sent.id)
        return sent
    except Exception:
        return None


async def _debounce_indexer(client, bot_id, user_id, session_id):
    """Wait until user stops forwarding files for 3 seconds, then show indexed panel."""
    try:
        while True:
            await asyncio.sleep(2.5)
            last_time = _LAST_MSG_TIME.get((bot_id, user_id), 0)
            if time.time() - last_time >= 2.5:
                break

        async with _lock(client, user_id):
            session = mongo_db.custom_batch_sessions.find_one({"session_id": session_id, "active": True})
            if not session:
                return
            count = len(session.get("messages", []))
            mongo_db.custom_batch_sessions.update_one(
                {"_id": session["_id"]},
                {"$set": {"status": "indexed", "updated_at": int(time.time())}}
            )
            await _replace_panel(
                client,
                session,
                _text_indexed(count),
                _controls_indexed(session["session_id"]),
            )
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        _INDEX_TASKS.pop((bot_id, user_id), None)


async def custom_batch(client, message):
    if not cmd.is_owner_or_mod(client, message.from_user.id) and cmd.bot_record(client).get("mode", "private") == "private":
        return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    async with _lock(client, message.from_user.id):
        key = (int(client.me.id), int(message.from_user.id))
        old_task = _INDEX_TASKS.pop(key, None)
        if old_task and not old_task.done():
            old_task.cancel()

        try:
            from link_modules import single_link
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
            "status": "ready",
            "active": True,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        result = mongo_db.custom_batch_sessions.insert_one(doc)
        session = mongo_db.custom_batch_sessions.find_one({"_id": result.inserted_id})
        await _replace_panel(client, session, _text_initial(0), _controls_initial(session_id))
    raise StopPropagation


async def capture_message(client, message):
    if mongo_db is None or not message.from_user or not message.chat:
        return
    if message.chat.type.value != "private":
        return
    if message.text and message.text.startswith("/"):
        return

    key = (int(client.me.id), int(message.from_user.id))
    _LAST_MSG_TIME[key] = time.time()

    async with _lock(client, message.from_user.id):
        session = _session(client, message.from_user.id)
        if not session or not session.get("active"):
            return

        messages = list(session.get("messages", []))
        if len(messages) >= MAX_FILES:
            raise StopPropagation

        item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
        try:
            from config import LOG_CHANNEL
            rec_db = cmd.bot_record(client)
            db_ch = rec_db.get("database_channel") or rec_db.get("db_channel") or LOG_CHANNEL
            if db_ch:
                copied = await message.copy(chat_id=int(db_ch))
                item = {"chat_id": int(db_ch), "message_id": int(copied.id)}
        except Exception:
            pass
        if any(x.get("chat_id") == item["chat_id"] and x.get("message_id") == item["message_id"] for x in messages):
            raise StopPropagation

        messages.append(item)
        session["messages"] = messages

        is_indexing = (session.get("status") == "indexing")
        if not is_indexing:
            mongo_db.custom_batch_sessions.update_one(
                {"_id": session["_id"], "active": True},
                {"$set": {"messages": messages, "status": "indexing", "updated_at": int(time.time())}}
            )
            session["status"] = "indexing"
            await _replace_panel(client, session, _text_indexing(), _controls_indexing(session["session_id"]))
        else:
            mongo_db.custom_batch_sessions.update_one(
                {"_id": session["_id"], "active": True},
                {"$set": {"messages": messages, "updated_at": int(time.time())}}
            )

        curr_task = _INDEX_TASKS.get(key)
        if not curr_task or curr_task.done():
            _INDEX_TASKS[key] = asyncio.create_task(
                _debounce_indexer(client, int(client.me.id), int(message.from_user.id), session["session_id"])
            )

        raise StopPropagation


async def _generate(client, query, session):
    messages = list(session.get("messages", []))[:MAX_FILES]
    if not messages:
        return await query.answer("Forward or send at least one message first.", show_alert=True)

    links = mongo_db.custom_batch_links
    token = secrets.token_urlsafe(18)
    rec = cmd.bot_record(client)
    protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    doc = {
        "token": token,
        "alt_tokens": [token, f"batch_{token}"],
        "bot_id": client.me.id,
        "owner_id": int(session["user_id"]),
        "messages": messages,
        "protected": protected,
        "created_at": int(time.time()),
    }
    links.update_one({"token": token}, {"$set": doc}, upsert=True)
    links.update_one({"token": f"batch_{token}"}, {"$set": doc}, upsert=True)

    username = (await client.get_me()).username
    url = f"https://t.me/{username}?start=batch_{token}"
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
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy Link 📋", url=f"https://t.me/share/url?url={shown}"),
            InlineKeyboardButton("📢 SHARE URL 📢", url=f"https://t.me/share/url?url={shown}")
        ]
    ])
    await client.send_message(int(session["user_id"]), text, reply_markup=markup, disable_web_page_preview=True)
    log_ch = rec.get("log_channel")
    if log_ch:
        try:
            await client.send_message(
                chat_id=int(log_ch),
                text=f"📦 <b>NEW CUSTOM BATCH LINK GENERATED:</b>\n\n👤 <b>By:</b> <code>{session['user_id']}</code>\n📊 <b>Total Messages:</b> {len(messages)}\n🔗 {shown}",
                disable_web_page_preview=True
            )
        except Exception:
            pass

    key = (int(client.me.id), int(session["user_id"]))

    task = _INDEX_TASKS.pop(key, None)
    if task and not task.done():
        task.cancel()
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
        elif action == "continue":
            key = (int(client.me.id), int(query.from_user.id))
            task = _INDEX_TASKS.pop(key, None)
            if task and not task.done():
                task.cancel()
            count = len(session.get("messages", []))
            mongo_db.custom_batch_sessions.update_one(
                {"_id": session["_id"]},
                {"$set": {"status": "ready", "updated_at": int(time.time())}}
            )
            await _replace_panel(
                client,
                session,
                _text_initial(count),
                _controls_initial(session_id),
            )
            await query.answer("Ready! Send or forward more files now.")
        elif action == "cancel":
            key = (int(client.me.id), int(query.from_user.id))
            task = _INDEX_TASKS.pop(key, None)
            if task and not task.done():
                task.cancel()

            old_chat = session.get("control_chat_id")
            old_msg = session.get("control_message_id")
            if old_chat and old_msg:
                try:
                    await client.delete_messages(int(old_chat), int(old_msg))
                except Exception:
                    pass
            mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})
            await client.send_message(int(query.from_user.id), "❌ <b>Batch session cancelled. All temporary stored files cleared.</b>")
            await query.answer("Cancelled.")
    raise StopPropagation


async def batch_start(client, message):
    if len(message.command) != 2 or not message.command[1].startswith("batch_"):
        return
    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    raw_cmd = message.command[1]
    candidates = [raw_cmd]
    if raw_cmd.startswith("batch_"):
        candidates.append(raw_cmd[6:])
    if "_" in raw_cmd:
        candidates.append(raw_cmd.split("_", 1)[1])
    try:
        pad = (4 - len(raw_cmd) % 4) % 4
        dec = base64.urlsafe_b64decode(raw_cmd + "=" * pad).decode("utf-8", errors="ignore")
        if dec:
            candidates.append(dec)
            if dec.startswith("batch_"):
                candidates.append(dec[6:])
            if "_" in dec:
                candidates.append(dec.split("_", 1)[1])
    except Exception:
        pass

    record = None
    for cand in candidates:
        if cand:
            record = mongo_db.custom_batch_links.find_one({"token": cand})
            if record:
                break

    if not record:
        await message.reply("❌ Invalid or expired batch link.")
        raise StopPropagation

    payload = message.command[1]
    access_res = await cmd.access_verification(client, message.from_user.id, payload)
    if isinstance(access_res, tuple):
        v_text, access_markup = access_res
    else:
        v_text, access_markup = "<b>🔐 Please verify first to access this batch.</b>", access_res
    if access_markup:
        await message.reply(v_text, reply_markup=access_markup, disable_web_page_preview=True)
        raise StopPropagation
    if await cmd.send_fsub_prompt(client, message, payload):
        raise StopPropagation

    messages = list(record.get("messages", []))
    if not messages:
        await message.reply("❌ This batch contains no messages.")
        raise StopPropagation

    rec = cmd.bot_record(client)
    is_protect = bool(record.get("protected", False)) or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

    custom_btns = rec.get("custom_buttons", [])
    markup = None
    if custom_btns:
        rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
        if rows:
            markup = InlineKeyboardMarkup(rows)

    custom_cap = rec.get("custom_caption")

    await message.reply(f"📦 <b>Sending {len(messages)} messages...</b>")
    for item in messages:
        c_id = int(item["chat_id"])
        m_id = int(item["message_id"])
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(c_id, m_id)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        try:
            await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=c_id,
                message_id=m_id,
                caption=caption_to_use,
                parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                reply_markup=markup,
                protect_content=is_protect,
            )
            await asyncio.sleep(0.05)
        except Exception:
            try:
                await client.copy_message(
                    chat_id=message.from_user.id,
                    from_chat_id=c_id,
                    message_id=m_id,
                    caption=caption_to_use,
                    reply_markup=markup,
                    protect_content=is_protect,
                )
                await asyncio.sleep(0.05)
            except Exception:
                continue
    await message.reply("✅ <b>Batch delivery completed.</b>")
    raise StopPropagation


def register(client, base_group=-101):
    private = filters.private
    client.add_handler(MessageHandler(batch_start, filters.command("start") & private), group=base_group)
    client.add_handler(MessageHandler(custom_batch, filters.command("custom_batch") & private), group=base_group)
    client.add_handler(MessageHandler(capture_message, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(callback, filters.regex(r"^cb_(generate|cancel|continue)_[A-Za-z0-9_-]+$")), group=base_group)
    return client
