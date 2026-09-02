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
from clone_plugins.users_api import get_user, get_short_link, format_caption, format_auto_delete_time
from plugins.clone import mongo_db
from settings_modules.thumbnail import get_cached_thumb_path, save_thumbnail_media
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

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
    sess = mongo_db.custom_batch_sessions.find_one({"bot_id": client.me.id, "user_id": int(user_id), "active": True})
    if sess:
        updated = sess.get("updated_at") or sess.get("created_at") or 0
        if time.time() - updated > 1800:
            mongo_db.custom_batch_sessions.delete_one({"_id": sess["_id"]})
            return None
    return sess


def _controls_initial(session_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CONTINUE OR GENERATE LINK", callback_data=f"cb_continue_{session_id}")],
        [InlineKeyboardButton("SET THUMBNAIL", callback_data=f"cb_thumb_{session_id}")],
        [InlineKeyboardButton("CANCEL YOUR PROCESS", callback_data=f"cb_cancel_{session_id}")],
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
            InlineKeyboardButton("🖼️ SET THUMBNAIL", callback_data=f"cb_thumb_{session_id}"),
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
            "When finished, tap <b>CONTINUE OR GENERATE LINK</b>."
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
    """Wait until user stops forwarding files for 2.5 seconds, then show indexed panel."""
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


async def custom_batch_cmd(client, message):
    from settings_modules.active_deactive import check_clone_status_or_block
    if await check_clone_status_or_block(client, message):
        return

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
            "session_thumbnail": None,
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
        cmd_name = message.text.split()[0].lower()
        if cmd_name == "/cancel":
            key = (int(client.me.id), int(message.from_user.id))
            task = _INDEX_TASKS.pop(key, None)
            if task and not task.done():
                task.cancel()
            _LAST_MSG_TIME.pop(key, None)
            mongo_db.custom_batch_sessions.delete_many({"bot_id": client.me.id, "user_id": int(message.from_user.id)})
            await message.reply("❌ <b>Custom batch process cancelled.</b>")
            raise StopPropagation
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
    session_thumb = session.get("session_thumbnail")
    session_thumb_path = session.get("session_thumbnail_path")
    doc = {
        "token": token,
        "alt_tokens": [token, f"batch_{token}"],
        "bot_id": client.me.id,
        "owner_id": int(session["user_id"]),
        "messages": messages,
        "protected": protected,
        "custom_thumbnail": session_thumb,
        "custom_thumb_path": session_thumb_path,
        "single_thumbnail": session_thumb,
        "single_thumbnail_path": session_thumb_path,
        "created_at": int(time.time()),
    }
    links.update_one({"token": token}, {"$set": doc}, upsert=True)
    links.update_one({"token": f"batch_{token}"}, {"$set": doc}, upsert=True)

    username = (await client.get_me()).username
    url = f"https://t.me/{username}?start=batch_{token}"
    from settings_modules.link_shortener import get_shortened_link_if_enabled
    shown = await get_shortened_link_if_enabled(client, int(session["user_id"]), url)

    try:
        await query.message.delete()
    except Exception:
        pass

    old_chat = session.get("control_chat_id")
    old_msg = session.get("control_message_id")
    if old_chat and old_msg:
        try:
            await client.delete_messages(int(old_chat), int(old_msg))
        except Exception:
            pass

    mongo_db.custom_batch_sessions.delete_one({"_id": session["_id"]})

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
    if data.startswith("cb_deliv_cancel_"):
        _ACTIVE_CUSTOM_DELIVERIES = getattr(custom_batch_cmd, "_active_deliveries", {})
        _ACTIVE_CUSTOM_DELIVERIES[(int(client.me.id), int(query.from_user.id))] = False
        await query.answer("Delivery cancelled.")
        try:
            await query.message.delete()
        except Exception:
            pass
        raise StopPropagation

    parts = data.split("_", 2)
    if len(parts) != 3 or parts[0] != "cb":
        return
    action, session_id = parts[1], parts[2]
    if mongo_db is None:
        return await query.answer("Database is not configured.", show_alert=True)

    async with _lock(client, query.from_user.id):
        session = mongo_db.custom_batch_sessions.find_one({"session_id": session_id})
        if not session or int(session.get("user_id", 0)) != int(query.from_user.id):
            if action == "cancel":
                mongo_db.custom_batch_sessions.delete_many({"bot_id": client.me.id, "user_id": int(query.from_user.id)})
                try:
                    await query.message.delete()
                except Exception:
                    pass
                return await query.answer("Cancelled.")
            return await query.answer("This batch session is not yours or has expired.", show_alert=True)

        if action == "generate":
            await _generate(client, query, session)
        elif action == "continue":
            key = (int(client.me.id), int(query.from_user.id))
            task = _INDEX_TASKS.pop(key, None)
            if task and not task.done():
                task.cancel()
            count = len(session.get("messages", []))
            if count > 0:
                await _generate(client, query, session)
            else:
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
                await query.answer("Ready! Send or forward your files now.")
        elif action == "thumb":
            user_id = int(query.from_user.id)
            sess_token = start_user_session(user_id, f"cb_thumb_{session_id}")
            try:
                await query.answer()
            except Exception:
                pass
            prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=f"cb_continue_{session_id}")]])
            p_msg = await client.send_message(
                chat_id=user_id,
                text="🖼️ <b>SEND ME A PICTURE FOR THIS BATCH THUMBNAIL.</b>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                reply_markup=prompt_markup
            )
            async def _cb_thumb_worker():
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    clear_user_session(user_id)
                    return
                if not is_user_session_active(user_id, sess_token):
                    return
                t = (ans.text or ans.caption or "").strip()
                if t == "/cancel":
                    clear_user_session(user_id)
                    if p_msg:
                        try:
                            await p_msg.delete()
                        except Exception:
                            pass
                    try:
                        await ans.delete()
                    except Exception:
                        pass
                    await client.send_message(user_id, "❌ <b>Thumbnail setting cancelled. Now send your files:</b>")
                    return
                if ans.photo:
                    photo_id = ans.photo.file_id
                    local_path = await save_thumbnail_media(client, ans, user_id, prefix=f"cb_{session_id}")
                    mongo_db.custom_batch_sessions.update_one(
                        {"session_id": session_id},
                        {"$set": {"session_thumbnail": photo_id, "session_thumbnail_path": local_path}}
                    )
                    clear_user_session(user_id)
                    if p_msg:
                        try:
                            await p_msg.delete()
                        except Exception:
                            pass
                    try:
                        await ans.delete()
                    except Exception:
                        pass
                    await client.send_message(
                        chat_id=user_id,
                        text="✅ <b>THUMBNAIL SAVED FOR THIS BATCH!</b>\n\n<b>NOW SEND YOUR FILES WHICH YOU WANT TO STORE:</b>"
                    )
                else:
                    clear_user_session(user_id)
                    await client.send_message(user_id, "⚠️ <b>Invalid photo. Process cancelled. Now send your files:</b>")
            asyncio.create_task(_cb_thumb_worker())
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
    if len(message.command) != 2:
        return
    if mongo_db is None:
        return
    payload = message.command[1]
    if not (payload.startswith("batch_") or payload.startswith("bat_")):
        token = payload
        record = mongo_db.custom_batch_links.find_one({"token": token})
        if not record:
            return
    else:
        token = payload.split("_", 1)[1]
        record = mongo_db.custom_batch_links.find_one({"token": token}) or mongo_db.custom_batch_links.find_one({"token": f"batch_{token}"})
        if not record:
            try:
                pad = (4 - len(payload) % 4) % 4
                dec = base64.urlsafe_b64decode(payload + "=" * pad).decode("utf-8", errors="ignore")
                if "_" in dec:
                    dec_tok = dec.split("_", 1)[1]
                    record = mongo_db.custom_batch_links.find_one({"token": dec_tok})
            except Exception:
                pass
        if not record:
            await message.reply("❌ This custom batch link is invalid or expired.")
            raise StopPropagation

    access_res = await cmd.access_verification(client, message.from_user.id, payload)
    v_text = None
    access_markup = None
    v_photo = None
    free_notice = None
    if isinstance(access_res, (tuple, list)):
        v_text = access_res[0]
        access_markup = access_res[1] if len(access_res) > 1 else None
        v_photo = access_res[2] if len(access_res) > 2 else None
        free_notice = access_res[3] if len(access_res) > 3 else None
    elif access_res:
        v_text, access_markup = "<b>🔐 Please verify first to access this batch.</b>", access_res
    if access_markup:
        await cmd.send_verify_prompt(client, message, v_text, access_markup, v_photo)
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
    invert_cap = bool(rec.get("invert_caption", False))
    spoiler_anim = bool(rec.get("spoiler_animation", False))
    batch_thumb = (
        record.get("single_thumbnail_path")
        or record.get("single_thumbnail")
        or record.get("custom_thumb_path")
        or record.get("custom_thumbnail")
        or rec.get("custom_thumb_path")
        or rec.get("custom_thumbnail")
    )

    from settings_modules.update_channel import send_wait_message
    delivery_key = (int(client.me.id), int(message.from_user.id))
    _ACTIVE_CUSTOM_DELIVERIES = getattr(custom_batch_cmd, "_active_deliveries", {})
    custom_batch_cmd._active_deliveries = _ACTIVE_CUSTOM_DELIVERIES
    _ACTIVE_CUSTOM_DELIVERIES[delivery_key] = True

    wait_msg = await send_wait_message(client, message, cancel_callback_data=f"cb_deliv_cancel_{token}")
    delivered_messages = []
    for item in messages:
        if not _ACTIVE_CUSTOM_DELIVERIES.get(delivery_key, False):
            break
        c_id = int(item["chat_id"])
        m_id = int(item["message_id"])
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(c_id, m_id)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        delivered = None
        if batch_thumb:
            try:
                src_msg = await client.get_messages(c_id, m_id)
                thumb_path = await get_cached_thumb_path(client, batch_thumb)
                if src_msg and thumb_path and os.path.exists(thumb_path):
                    if src_msg.video:
                        send_kw = {
                            "chat_id": message.from_user.id,
                            "video": src_msg.video.file_id,
                            "caption": caption_to_use,
                            "thumb": thumb_path,
                            "duration": getattr(src_msg.video, "duration", 0),
                            "width": getattr(src_msg.video, "width", 0),
                            "height": getattr(src_msg.video, "height", 0),
                            "supports_streaming": True,
                            "reply_markup": markup,
                            "protect_content": is_protect,
                        }
                        if caption_to_use:
                            send_kw["parse_mode"] = enums.ParseMode.HTML
                        if invert_cap:
                            send_kw["show_caption_above_media"] = True
                        if spoiler_anim:
                            send_kw["has_spoiler"] = True
                        try:
                            delivered = await client.send_video(**send_kw)
                        except Exception:
                            pass
                    elif src_msg.document:
                        send_kw_d = {
                            "chat_id": message.from_user.id,
                            "document": src_msg.document.file_id,
                            "caption": caption_to_use,
                            "thumb": thumb_path,
                            "reply_markup": markup,
                            "protect_content": is_protect,
                        }
                        if caption_to_use:
                            send_kw_d["parse_mode"] = enums.ParseMode.HTML
                        try:
                            delivered = await client.send_document(**send_kw_d)
                        except Exception:
                            pass
            except Exception:
                pass

        if not delivered:
            base_kw = {
                "chat_id": message.from_user.id,
                "from_chat_id": c_id,
                "message_id": m_id,
                "caption": caption_to_use,
                "reply_markup": markup,
                "protect_content": is_protect,
            }
            if caption_to_use:
                base_kw["parse_mode"] = enums.ParseMode.HTML

            attempts = []
            kw1 = dict(base_kw)
            if invert_cap:
                kw1["invert_media"] = True
            if spoiler_anim:
                kw1["has_spoiler"] = True
            attempts.append(kw1)

            if invert_cap or spoiler_anim:
                kw2 = dict(base_kw)
                if invert_cap:
                    kw2["show_caption_above_media"] = True
                if spoiler_anim:
                    kw2["has_spoiler"] = True
                attempts.append(kw2)

            if spoiler_anim:
                attempts.append({**base_kw, "has_spoiler": True})

            attempts.append(base_kw)
            fb_no_pm = dict(base_kw)
            fb_no_pm.pop("parse_mode", None)
            attempts.append(fb_no_pm)

            for attempt_kw in attempts:
                try:
                    delivered = await client.copy_message(**attempt_kw)
                    await asyncio.sleep(0.1)
                    break
                except Exception:
                    continue
                    
        if delivered:
            delivered_messages.append(delivered)

    _ACTIVE_CUSTOM_DELIVERIES.pop(delivery_key, None)
    if wait_msg:
        try:
            await wait_msg.delete()
        except Exception:
            pass

    try:
        ad_enabled = bool(rec.get("auto_delete_enabled", False))
        ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 0) or 0) * 60) or 0)
        if ad_enabled and ad_sec > 0 and delivered_messages:
            from link_modules.auto_delete_delivery import schedule_auto_delete
            await schedule_auto_delete(client, message.from_user.id, delivered_messages, ad_sec)
    except Exception:
        pass

    if free_notice and delivered_messages:
        try:
            await client.send_message(message.from_user.id, free_notice)
        except Exception:
            pass

    raise StopPropagation


def register(client, base_group=-100):
    client.add_handler(MessageHandler(custom_batch_cmd, filters.command(["custom_batch"]) & filters.private), group=base_group)
    client.add_handler(MessageHandler(capture_message, filters.private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(callback, filters.regex(r"^cb_")), group=base_group)
    return client
