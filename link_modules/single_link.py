"""
Single file / media shareable link generator and delivery handler.
Main command in menus: /getlink
Aliases supported: /link, /genlink
"""
import base64
import os
import secrets
import time
import asyncio
from pyrogram import StopPropagation, filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.users_api import get_user, get_short_link, format_caption, format_auto_delete_time
from plugins.clone import mongo_db
from clone_plugins.commands import bot_record, force_markup, access_verification, send_fsub_prompt
from settings_modules.thumbnail import get_cached_thumb_path, save_thumbnail_media

_PENDING = {}

def _payload(token: str) -> str:
    return base64.urlsafe_b64encode(f"msg_{token}".encode()).decode().rstrip("=")

def _decode(payload: str):
    if not payload:
        return None
    if payload.startswith("msg_") or payload.startswith("msM_"):
        return payload.split("_", 1)[1]
    try:
        pad = (4 - len(payload) % 4) % 4
        raw = base64.urlsafe_b64decode(payload + "=" * pad).decode("utf-8", errors="ignore")
        if "_" in raw:
            prefix, token = raw.split("_", 1)
            if prefix.lower() in ("msg", "msm", "file", "filep") and token:
                return token
        return raw
    except Exception:
        pass
    return payload

def _batch_active(client, user_id):
    """Return True while this user is collecting a custom batch, channel batch, or special link."""
    try:
        from link_modules.special_link import is_special_link_active
        if is_special_link_active(client.me.id, user_id):
            return True
    except Exception:
        pass
    try:
        from link_modules.channel_batch import is_channel_batch_active
        if is_channel_batch_active(client.me.id, user_id):
            return True
    except Exception:
        pass
    try:
        if mongo_db is None:
            return False
        doc = mongo_db.batch_sessions.find_one({"bot_id": client.me.id, "user_id": int(user_id)})
        return bool(doc and doc.get("active"))
    except Exception:
        return False

async def genlink_prompt(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    if _batch_active(client, user_id):
        return

    key = (client.me.id, user_id)
    old = _PENDING.get(key)
    if isinstance(old, dict) and old.get("prompt_id"):
        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[old["prompt_id"]])
        except Exception:
            pass

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("CONTINUE OR GENERATE LINK", callback_data="sl_continue")],
        [InlineKeyboardButton("SET SINGLE FILE THUMBNAIL", callback_data="sl_thumb")],
        [InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]
    ])

    sent = await message.reply(
        "⚡ <b>GENERATE SINGLE LINK</b>\n\n"
        "<b>Choose an option below to proceed:</b>",
        reply_markup=markup,
        disable_web_page_preview=True
    )
    _PENDING[key] = {"step": "choice", "prompt_id": sent.id, "time": int(time.time())}
    raise StopPropagation

async def single_link_callback(client, query):
    if not query.from_user:
        return
    user_id = query.from_user.id
    data = query.data or ""
    key = (client.me.id, user_id)

    if data == "sl_cancel":
        _PENDING.pop(key, None)
        try:
            await query.message.edit_text("❌ <b>Link generation cancelled.</b>")
        except Exception:
            pass
        try:
            await query.answer("Cancelled")
        except Exception:
            pass
        return

    if data == "sl_continue":
        try:
            await query.answer()
        except Exception:
            pass
        _PENDING[key] = {"step": "message", "thumb": None, "thumb_path": None, "prompt_id": query.message.id, "time": int(time.time())}
        try:
            await query.message.edit_text(
                "⚡ <b>SEND ME YOUR MESSAGE WHICH YOU WANT TO STORE:</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]])
            )
        except Exception:
            pass
        return

    if data == "sl_thumb":
        try:
            await query.answer()
        except Exception:
            pass
        _PENDING[key] = {"step": "thumb", "prompt_id": query.message.id, "time": int(time.time())}
        try:
            await query.message.edit_text(
                "🖼️ <b>SEND ME A PICTURE FOR THIS LINK THUMBNAIL.</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]])
            )
        except Exception:
            pass
        return

async def capture_single(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    key = (client.me.id, user_id)

    # 1. Do NOT capture if a user session is active (e.g. setting QR pic, caption, etc.)
    try:
        from clone_plugins.sessions import _USER_SESSIONS
        if int(user_id) in _USER_SESSIONS:
            return
    except Exception:
        pass

    # 2. Do NOT capture if client is listening for input from this user/chat
    for attr in ("_listeners", "listeners"):
        try:
            d = getattr(client, attr, None)
            if isinstance(d, dict) and (user_id in d or message.chat.id in d):
                return
        except Exception:
            pass

    if _batch_active(client, user_id):
        return

    # 3. Only proceed if getlink/single link flow was initiated
    if key not in _PENDING:
        return

    txt = (message.text or message.caption or "").strip()
    if txt.startswith("/"):
        cmd = txt.split()[0].lower()
        if cmd in ("/link", "/getlink", "/genlink", "/batch", "/custom_batch", "/special_link", "/channel_batch", "/settings", "/start", "/help"):
            return

    if txt.lower() == "/cancel":
        state = _PENDING.pop(key, None)
        if isinstance(state, dict) and state.get("prompt_id"):
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=[state["prompt_id"]])
            except Exception:
                pass
        try:
            await message.delete()
        except Exception:
            pass
        await message.reply("❌ Cancelled.")
        raise StopPropagation

    state = _PENDING.get(key)
    if isinstance(state, dict) and state.get("step") == "thumb":
        if message.photo:
            thumb_id = message.photo.file_id
            local_path = await save_thumbnail_media(client, message, message.from_user.id, prefix=f"sl_{int(time.time())}")
            
            if state.get("prompt_id"):
                try:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=[state["prompt_id"]])
                except Exception:
                    pass
            try:
                await message.delete()
            except Exception:
                pass

            new_prompt = await message.reply(
                "✅ <b>THUMBNAIL SAVED FOR THIS LINK!</b>\n\n"
                "<b>NOW SEND YOUR FILE / VIDEO WHICH YOU WANT TO STORE:</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
            _PENDING[key] = {
                "step": "message",
                "thumb": thumb_id,
                "thumb_path": local_path,
                "prompt_id": new_prompt.id if new_prompt else None,
                "time": int(time.time())
            }
            raise StopPropagation
        else:
            await message.reply("⚠️ <b>Please send a valid photo picture. Send /cancel to abort.</b>")
            raise StopPropagation

    thumb = state.get("thumb") if isinstance(state, dict) else None
    thumb_path = state.get("thumb_path") if isinstance(state, dict) else None
    prompt_id_to_delete = state.get("prompt_id") if isinstance(state, dict) else None
    _PENDING.pop(key, None)

    if prompt_id_to_delete:
        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[prompt_id_to_delete])
        except Exception:
            pass

    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    from config import LOG_CHANNEL
    rec = bot_record(client)
    db_ch = rec.get("database_channel") or rec.get("db_channel") or LOG_CHANNEL
    source_chat_id = int(message.chat.id)
    source_message_id = int(message.id)

    # Extract file metadata
    file_id = None
    media_type = None
    duration = 0
    width = 0
    height = 0
    file_name = None

    if message.video:
        file_id = message.video.file_id
        media_type = "video"
        duration = getattr(message.video, "duration", 0)
        width = getattr(message.video, "width", 0)
        height = getattr(message.video, "height", 0)
        file_name = getattr(message.video, "file_name", None)
    elif message.document:
        file_id = message.document.file_id
        media_type = "document"
        file_name = getattr(message.document, "file_name", None)
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "animation"
        duration = getattr(message.animation, "duration", 0)
        width = getattr(message.animation, "width", 0)
        height = getattr(message.animation, "height", 0)
        file_name = getattr(message.animation, "file_name", None)
    elif message.photo:
        file_id = message.photo.file_id
        media_type = "photo"
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
        duration = getattr(message.audio, "duration", 0)
        file_name = getattr(message.audio, "file_name", None)

    if db_ch:
        try:
            copied = await message.copy(chat_id=int(db_ch))
            source_chat_id = int(db_ch)
            source_message_id = int(copied.id)
        except Exception:
            pass

    log_ch = rec.get("log_channel")
    if log_ch:
        try:
            await message.forward(chat_id=int(log_ch))
        except Exception:
            try:
                await message.copy(chat_id=int(log_ch))
            except Exception:
                pass

    token = secrets.token_urlsafe(18)
    b64_tok = _payload(token)
    msg_tok = f"msg_{token}"

    doc = {
        "bot_id": client.me.id,
        "token": token,
        "alt_tokens": [token, msg_tok, b64_tok],
        "source_chat_id": source_chat_id,
        "source_message_id": source_message_id,
        "owner_id": int(message.from_user.id),
        "created_at": int(time.time()),
        "single_thumbnail": thumb,
        "single_thumbnail_path": thumb_path,
        "file_id": file_id,
        "media_type": media_type,
        "duration": duration,
        "width": width,
        "height": height,
        "file_name": file_name,
        "file_caption": message.caption or None,
    }
    mongo_db.share_links.update_one({"token": token}, {"$set": doc}, upsert=True)
    mongo_db.share_links.update_one({"token": msg_tok}, {"$set": doc}, upsert=True)
    mongo_db.share_links.update_one({"token": b64_tok}, {"$set": doc}, upsert=True)

    username = (await client.get_me()).username
    link = f"https://t.me/{username}?start=msg_{token}" 
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy Link 📋", url=f"https://t.me/share/url?url={link}"),
            InlineKeyboardButton("📢 SHARE URL 📢", url=f"https://t.me/share/url?url={link}")
        ]
    ])

    note = "\n\n🖼️ <b>Custom thumbnail cover set!</b>" if (thumb or thumb_path) else ""
    await message.reply(
        "⚡ <b>HERE IS YOUR LINK :</b>\n\n"
        f"🔗 {link}{note}",
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    raise StopPropagation

async def open_single(client, message):
    if len(message.command) != 2:
        return
    if mongo_db is None:
        return

    payload_val = message.command[1]
    candidates = [payload_val]
    if "_" in payload_val:
        candidates.append(payload_val.split("_", 1)[1])
    try:
        pad = (4 - len(payload_val) % 4) % 4
        dec = base64.urlsafe_b64decode(payload_val + "=" * pad).decode("utf-8", errors="ignore")
        if dec:
            candidates.append(dec)
            if "_" in dec:
                candidates.append(dec.split("_", 1)[1])
    except Exception:
        pass

    record = None
    for cand in candidates:
        if cand:
            record = mongo_db.share_links.find_one({"token": cand})
            if record:
                break
    if not record:
        token = _decode(payload_val)
        if token:
            record = mongo_db.share_links.find_one({"token": token})
    if not record:
        if payload_val.startswith("msg_") or payload_val.startswith("msM_") or payload_val.startswith("bXNN") or payload_val.startswith("bXNn"):
            await message.reply("❌ This link is invalid or expired.")
            raise StopPropagation
        return

    payload = message.command[1]
    access_res = await access_verification(client, message.from_user.id, payload)
    if isinstance(access_res, tuple):
        v_text, access_markup = access_res
    else:
        v_text, access_markup = "<b>🔐 Please verify first to access this file.</b>", access_res
    if access_markup:
        await message.reply(v_text, reply_markup=access_markup, disable_web_page_preview=True)
        raise StopPropagation
    if await send_fsub_prompt(client, message, payload):
        raise StopPropagation

    try:
        rec = bot_record(client)
        is_protect = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

        custom_btns = rec.get("custom_buttons", [])
        markup = None
        if custom_btns:
            rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
            if rows:
                markup = InlineKeyboardMarkup(rows)

        source_chat = int(record["source_chat_id"])
        source_mid = int(record["source_message_id"])

        custom_cap = rec.get("custom_caption")
        invert_cap = bool(rec.get("invert_caption", False))
        spoiler_anim = bool(rec.get("spoiler_animation", False))
        caption_to_use = None

        thumb_to_use = (
            record.get("single_thumbnail_path")
            or record.get("single_thumbnail")
            or record.get("custom_thumb_path")
            or record.get("custom_thumbnail")
            or rec.get("custom_thumb_path")
            or rec.get("custom_thumbnail")
        )

        thumb_path = None
        if thumb_to_use:
            thumb_path = await get_cached_thumb_path(client, thumb_to_use)

        file_id = record.get("file_id")
        media_type = record.get("media_type")
        duration = record.get("duration", 0)
        width = record.get("width", 0)
        height = record.get("height", 0)
        file_name = record.get("file_name")

        # Fetch source message if needed
        src_msg = None
        try:
            src_msg = await client.get_messages(source_chat, source_mid)
        except Exception:
            try:
                from AshCore.bot import StreamBot
                src_msg = await StreamBot.get_messages(source_chat, source_mid)
            except Exception:
                pass

        if custom_cap:
            try:
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap
        elif src_msg and src_msg.caption:
            caption_to_use = src_msg.caption.html if hasattr(src_msg.caption, "html") else src_msg.caption
        elif record.get("file_caption"):
            caption_to_use = record.get("file_caption")

        delivered = None

        # 1. Direct send_video if video file
        if media_type == "video" or (src_msg and src_msg.video):
            vid_id = file_id or (src_msg.video.file_id if src_msg and src_msg.video else None)
            if vid_id:
                kw = {
                    "chat_id": message.from_user.id,
                    "video": vid_id,
                    "caption": caption_to_use,
                    "supports_streaming": True,
                    "reply_markup": markup,
                    "protect_content": is_protect,
                }
                if thumb_path and os.path.exists(thumb_path):
                    kw["thumb"] = thumb_path
                if duration or (src_msg and src_msg.video and getattr(src_msg.video, "duration", 0)):
                    kw["duration"] = duration or src_msg.video.duration
                if width or (src_msg and src_msg.video and getattr(src_msg.video, "width", 0)):
                    kw["width"] = width or src_msg.video.width
                if height or (src_msg and src_msg.video and getattr(src_msg.video, "height", 0)):
                    kw["height"] = height or src_msg.video.height
                if file_name or (src_msg and src_msg.video and getattr(src_msg.video, "file_name", None)):
                    kw["file_name"] = file_name or src_msg.video.file_name
                if caption_to_use:
                    kw["parse_mode"] = enums.ParseMode.HTML
                if invert_cap:
                    kw["show_caption_above_media"] = True
                if spoiler_anim:
                    kw["has_spoiler"] = True
                try:
                    delivered = await client.send_video(**kw)
                except Exception:
                    pass

        # 2. Document file
        if not delivered and (media_type == "document" or (src_msg and src_msg.document)):
            doc_id = file_id or (src_msg.document.file_id if src_msg and src_msg.document else None)
            if doc_id:
                kw_d = {
                    "chat_id": message.from_user.id,
                    "document": doc_id,
                    "caption": caption_to_use,
                    "reply_markup": markup,
                    "protect_content": is_protect,
                }
                if thumb_path and os.path.exists(thumb_path):
                    kw_d["thumb"] = thumb_path
                if file_name or (src_msg and src_msg.document and getattr(src_msg.document, "file_name", None)):
                    kw_d["file_name"] = file_name or src_msg.document.file_name
                if caption_to_use:
                    kw_d["parse_mode"] = enums.ParseMode.HTML
                try:
                    delivered = await client.send_document(**kw_d)
                except Exception:
                    pass

        # 3. Fallback: Copy message
        if not delivered:
            attempts = []
            base_kw = {
                "chat_id": message.from_user.id,
                "from_chat_id": source_chat,
                "message_id": source_mid,
                "caption": caption_to_use,
                "reply_markup": markup,
                "protect_content": is_protect,
            }
            if caption_to_use:
                base_kw["parse_mode"] = enums.ParseMode.HTML
            kw1 = dict(base_kw)
            if invert_cap:
                kw1["invert_media"] = True
            if spoiler_anim:
                kw1["has_spoiler"] = True
            attempts.append(kw1)
            attempts.append(base_kw)
            for attempt_kw in attempts:
                try:
                    delivered = await client.copy_message(**attempt_kw)
                    if delivered:
                        break
                except Exception:
                    continue

        # Schedule auto delete if enabled
        try:
            ad_enabled = bool(rec.get("auto_delete_enabled", False))
            ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 0) or 0) * 60) or 0)
            if ad_enabled and ad_sec > 0 and delivered:
                from link_modules.auto_delete_delivery import schedule_auto_delete
                await schedule_auto_delete(client, message.from_user.id, [delivered], ad_sec)
        except Exception:
            pass

    except Exception:
        try:
            await message.reply("❌ Failed to deliver file. Please try again.")
        except Exception:
            pass
    raise StopPropagation

def register(client, base_group=-100):
    private = filters.private
    client.add_handler(MessageHandler(genlink_prompt, filters.command(["link", "getlink", "genlink"]) & private), group=base_group)
    client.add_handler(MessageHandler(capture_single, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(single_link_callback, filters.regex(r"^sl_")), group=base_group)
    return client
