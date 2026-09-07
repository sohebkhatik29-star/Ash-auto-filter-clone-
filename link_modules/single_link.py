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
from clone_plugins.commands import bot_record, force_markup, access_verification, send_fsub_prompt, send_verify_prompt
from settings_modules.thumbnail import get_cached_thumb_path, save_thumbnail_media

_SHARE_LINK_CACHE = {}  # token -> (expiry, record)
_SHARE_LINK_TTL = 300

def get_cached_share_link(cand):
    if not cand:
        return None
    now = time.time()
    if cand in _SHARE_LINK_CACHE:
        exp, r = _SHARE_LINK_CACHE[cand]
        if now < exp:
            return r
    if mongo_db is not None:
        try:
            r = mongo_db.share_links.find_one({"token": cand})
            if r:
                _SHARE_LINK_CACHE[cand] = (now + _SHARE_LINK_TTL, r)
                return r
        except Exception:
            pass
    return None

_PENDING = {}

def is_single_link_pending(bot_id: int, user_id: int) -> bool:
    """Return True if user is in an active /getlink workflow."""
    key = (int(bot_id), int(user_id))
    return key in _PENDING

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
    """Return True while this user is collecting a custom batch, channel batch, special link, or universal link."""
    try:
        from link_modules.universal_link import is_universal_link_active
        if is_universal_link_active(client.me.id, user_id):
            return True
    except Exception:
        pass
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

def _choice_markup(has_thumb: bool = False):
    if has_thumb:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("CONTINUE OR GENERATE LINK", callback_data="sl_continue")],
            [InlineKeyboardButton("🖼️ VIEW SINGLE THUMBNAIL", callback_data="sl_view_thumb")],
            [InlineKeyboardButton("🔄 CHANGE SINGLE THUMBNAIL", callback_data="sl_thumb")],
            [InlineKeyboardButton("🗑️ REMOVE SINGLE THUMBNAIL", callback_data="sl_del_thumb")],
            [InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("CONTINUE OR GENERATE LINK", callback_data="sl_continue")],
        [InlineKeyboardButton("SET SINGLE FILE THUMBNAIL", callback_data="sl_thumb")],
        [InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]
    ])

async def genlink_prompt(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    if _batch_active(client, user_id):
        return

    from settings_modules.active_deactive import check_clone_status_or_block
    if await check_clone_status_or_block(client, message):
        return

    from clone_plugins.auth import is_clone_authorized, UNAUTHORIZED_MESSAGE_TEXT, unauthorized_markup
    if not is_clone_authorized(client, user_id):
        await message.reply(UNAUTHORIZED_MESSAGE_TEXT, reply_markup=unauthorized_markup(client), disable_web_page_preview=True)
        raise StopPropagation

    key = (client.me.id, user_id)
    old = _PENDING.get(key)
    if isinstance(old, dict) and old.get("prompt_id"):
        try:
            await client.delete_messages(chat_id=message.chat.id, message_ids=[old["prompt_id"]])
        except Exception:
            pass

    has_thumb = bool(isinstance(old, dict) and (old.get("thumb") or old.get("thumb_path")))
    markup = _choice_markup(has_thumb)

    sent = await message.reply(
        "⚡ <b>GENERATE SINGLE LINK</b>\n\n"
        "<b>Choose an option below to proceed:</b>",
        reply_markup=markup,
        disable_web_page_preview=True
    )
    _PENDING[key] = {
        "step": "choice",
        "thumb": old.get("thumb") if isinstance(old, dict) else None,
        "thumb_path": old.get("thumb_path") if isinstance(old, dict) else None,
        "prompt_id": sent.id,
        "time": int(time.time())
    }
    raise StopPropagation

async def single_link_callback(client, query):
    if not query.from_user:
        return
    user_id = query.from_user.id

    from clone_plugins.auth import is_clone_authorized
    if not is_clone_authorized(client, user_id):
        try:
            await query.answer("⚠️ You are not my Master / Admin!", show_alert=True)
        except Exception:
            pass
        return
    data = query.data or ""
    key = (client.me.id, user_id)
    state = _PENDING.get(key) or {}

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
        cur_thumb = state.get("thumb")
        cur_path = state.get("thumb_path")
        _PENDING[key] = {
            "step": "message",
            "thumb": cur_thumb,
            "thumb_path": cur_path,
            "prompt_id": query.message.id,
            "time": int(time.time())
        }
        
        info_note = "\n\n<i>(Custom thumbnail attached)</i>" if (cur_thumb or cur_path) else "\n\n<i>(Bot permanent default thumbnail will be used)</i>"
        try:
            await query.message.edit_text(
                f"⚡ <b>SEND ME YOUR MESSAGE / FILE WHICH YOU WANT TO STORE:</b>{info_note}\n\n"
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
        _PENDING[key] = {
            "step": "thumb",
            "thumb": state.get("thumb"),
            "thumb_path": state.get("thumb_path"),
            "prompt_id": query.message.id,
            "time": int(time.time())
        }
        try:
            await query.message.edit_text(
                "🖼️ <b>SEND ME A PICTURE FOR THIS LINK THUMBNAIL.</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]])
            )
        except Exception:
            pass
        return

    if data == "sl_view_thumb":
        cur_thumb = state.get("thumb")
        cur_path = state.get("thumb_path")
        if not (cur_thumb or (cur_path and os.path.exists(cur_path))):
            try:
                await query.answer("No single custom thumbnail set for this link yet!", show_alert=True)
            except Exception:
                pass
            return
        
        try:
            await query.answer()
        except Exception:
            pass
        
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="sl_back_choice")]])
        photo_target = cur_thumb or cur_path
        try:
            await client.send_photo(
                chat_id=user_id,
                photo=photo_target,
                caption="🖼️ <b>SINGLE FILE THUMBNAIL FOR THIS LINK</b>",
                reply_markup=back_markup
            )
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception:
            pass
        return

    if data == "sl_del_thumb":
        state["thumb"] = None
        state["thumb_path"] = None
        _PENDING[key] = state
        try:
            await query.answer("Single File Thumbnail removed!", show_alert=True)
        except Exception:
            pass
        
        try:
            await query.message.edit_text(
                "🗑️ <b>Single File Thumbnail Removed!</b>\n\n"
                "<b>Now send your file / video to generate link (bot's default permanent thumbnail will be used), or choose an option below:</b>",
                reply_markup=_choice_markup(has_thumb=False)
            )
        except Exception:
            pass
        return

    if data == "sl_back_choice":
        try:
            await query.answer()
        except Exception:
            pass
        has_thumb = bool(state.get("thumb") or state.get("thumb_path"))
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await client.send_message(
            chat_id=user_id,
            text="⚡ <b>GENERATE SINGLE LINK</b>\n\n<b>Choose an option below to proceed:</b>",
            reply_markup=_choice_markup(has_thumb)
        )
        state["prompt_id"] = sent.id
        state["step"] = "choice"
        _PENDING[key] = state
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

            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🖼️ VIEW THUMBNAIL", callback_data="sl_view_thumb"),
                    InlineKeyboardButton("🗑️ REMOVE THUMBNAIL", callback_data="sl_del_thumb")
                ],
                [InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]
            ])

            new_prompt = await message.reply(
                "✅ <b>THUMBNAIL SAVED FOR THIS LINK!</b>\n\n"
                "<b>NOW SEND YOUR FILE / VIDEO WHICH YOU WANT TO STORE:</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
                reply_markup=markup
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
    raw_link = f"https://t.me/{username}?start=msg_{token}"
    from settings_modules.link_shortener import get_shortened_link_if_enabled
    link = await get_shortened_link_if_enabled(client, message.from_user.id, raw_link)
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy Link 📋", url=f"https://t.me/share/url?url={link}"),
            InlineKeyboardButton("📢 SHARE URL 📢", url=f"https://t.me/share/url?url={link}")
        ]
    ])

    if thumb or thumb_path:
        note = "\n\n🖼️ <b>Single File Custom Thumbnail applied to this link!</b>"
    elif rec.get("custom_thumbnail") or rec.get("custom_thumb_path"):
        note = "\n\n🖼️ <b>Bot Permanent Thumbnail will be applied!</b>"
    else:
        note = ""

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
            record = get_cached_share_link(cand)
            if record:
                break
    if not record:
        token = _decode(payload_val)
        if token:
            record = get_cached_share_link(token)
    if not record:
        if payload_val.startswith("msg_") or payload_val.startswith("msM_") or payload_val.startswith("bXNN") or payload_val.startswith("bXNn"):
            await message.reply("❌ This link is invalid or expired.")
            raise StopPropagation
        return

    payload = message.command[1]
    if await send_fsub_prompt(client, message, payload):
        raise StopPropagation

    access_res = await access_verification(client, message.from_user.id, payload)
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
        v_text, access_markup = "<b>🔐 Please verify first to access this file.</b>", access_res
    if access_markup:
        await send_verify_prompt(client, message, v_text, access_markup, v_photo)
        raise StopPropagation

    from settings_modules.update_channel import send_wait_message
    wait_msg = None
    try:
        wait_msg = await send_wait_message(client, message, cancel_callback_data=f"sl_cancel_{payload}", auto_delete_delay=0)
    except Exception:
        pass

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

        file_id = record.get("file_id")
        media_type = record.get("media_type")

        # Ultra-fast in-memory caption resolution (0 network calls, 0.000001s latency)
        if custom_cap:
            f_name = record.get("file_name") or "File"
            f_cap = record.get("file_caption") or ""
            f_sz = record.get("file_size") or ""
            if "{" in custom_cap:
                caption_to_use = format_caption(
                    custom_cap,
                    file_name=f_name,
                    file_size=str(f_sz),
                    orig_caption=f_cap
                )
            else:
                caption_to_use = custom_cap
        elif record.get("file_caption"):
            caption_to_use = record.get("file_caption")

        delivered = None

        # 1. PRIMARY: Instant send_cached_media with file_id (0.01s latency)
        if file_id:
            try:
                delivered = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_id,
                    caption=caption_to_use,
                    parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                    reply_markup=markup,
                    protect_content=is_protect,
                )
            except Exception:
                try:
                    delivered = await client.send_cached_media(
                        chat_id=message.from_user.id,
                        file_id=file_id,
                        protect_content=is_protect,
                    )
                except Exception:
                    pass

        # 2. SECONDARY: copy_message directly from source channel (0.05s latency)
        if not delivered:
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
            if invert_cap:
                base_kw["show_caption_above_media"] = True
            if spoiler_anim:
                base_kw["has_spoiler"] = True

            try:
                delivered = await client.copy_message(**base_kw)
            except Exception:
                try:
                    fb_kw = dict(base_kw)
                    fb_kw.pop("parse_mode", None)
                    fb_kw.pop("show_caption_above_media", None)
                    fb_kw.pop("has_spoiler", None)
                    delivered = await client.copy_message(**fb_kw)
                except Exception:
                    pass

        # 3. TERTIARY: StreamBot copy_message (master bot has access to source channel)
        if not delivered:
            try:
                from AshCore.bot import StreamBot
                delivered = await StreamBot.copy_message(**base_kw)
            except Exception:
                try:
                    delivered = await StreamBot.copy_message(
                        chat_id=message.from_user.id,
                        from_chat_id=source_chat,
                        message_id=source_mid,
                        protect_content=is_protect,
                    )
                except Exception:
                    pass

        # 4. QUATERNARY: send_video / send_document fallback
        if not delivered and file_id:
            detected_media_type = media_type or "video"
            if detected_media_type == "video":
                try:
                    delivered = await client.send_video(
                        chat_id=message.from_user.id,
                        video=file_id,
                        caption=caption_to_use,
                        parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                        reply_markup=markup,
                        protect_content=is_protect,
                        supports_streaming=True,
                    )
                except Exception:
                    pass
            elif detected_media_type == "document":
                try:
                    delivered = await client.send_document(
                        chat_id=message.from_user.id,
                        document=file_id,
                        caption=caption_to_use,
                        parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                        reply_markup=markup,
                        protect_content=is_protect,
                    )
                except Exception:
                    pass

        # IMMEDIATELY remove Please wait message when file arrives
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass

        # Schedule auto delete in background if enabled
        try:
            ad_enabled = bool(rec.get("auto_delete_enabled", False))
            ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 0) or 0) * 60) or 0)
            if ad_enabled and ad_sec > 0 and delivered:
                from link_modules.auto_delete_delivery import schedule_auto_delete
                asyncio.create_task(schedule_auto_delete(client, message.from_user.id, [delivered], ad_sec))
        except Exception:
            pass

        if free_notice and delivered:
            try:
                await client.send_message(message.from_user.id, free_notice)
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
