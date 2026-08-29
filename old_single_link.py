"""Single file / media shareable link generator and delivery handler.
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
        return bool(mongo_db.custom_batch_sessions.find_one({
            "bot_id": int(client.me.id),
            "user_id": int(user_id),
            "active": True,
        }))
    except Exception:
        return False


async def genlink_prompt(client, message):
    # Do not start a single-link capture while Custom Batch is active.
    if _batch_active(client, message.from_user.id):
        await message.reply("⚠️ Custom Batch is active. Use 🔗 GENERATE LINK on the batch panel when finished.")
        raise StopPropagation
    key = (client.me.id, message.from_user.id)
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("CONTINUE OR GENERATE LINK", callback_data="sl_continue")],
        [InlineKeyboardButton("SET SINGLE FILE THUMBNAIL", callback_data="sl_set_thumb")],
        [InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]
    ])
    prompt_msg = await message.reply(
        "⚡ <b>GENERATE SINGLE LINK</b>\n\n"
        "<b>Choose an option below to proceed:</b>",
        reply_markup=markup
    )
    _PENDING[key] = {
        "step": "init",
        "thumb": None,
        "thumb_path": None,
        "prompt_id": prompt_msg.id if prompt_msg else None,
        "time": int(time.time())
    }
    raise StopPropagation


async def single_link_callback(client, query):
    data = query.data or ""
    if not data.startswith("sl_"):
        return
    user_id = query.from_user.id
    key = (client.me.id, user_id)

    if data == "sl_continue":
        _PENDING[key] = {
            "step": "message",
            "thumb": None,
            "thumb_path": None,
            "prompt_id": query.message.id if query.message else None,
            "time": int(time.time())
        }
        try:
            await query.answer()
        except Exception:
            pass
        await query.message.edit_text(
            "<b>SEND ME YOUR MESSAGE WHICH YOU WANT TO STORE</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        raise StopPropagation

    if data == "sl_set_thumb":
        _PENDING[key] = {
            "step": "thumb",
            "thumb": None,
            "thumb_path": None,
            "prompt_id": query.message.id if query.message else None,
            "time": int(time.time())
        }
        try:
            await query.answer()
        except Exception:
            pass
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data="sl_cancel")]])
        await query.message.edit_text(
            "🖼️ <b>SEND ME A PICTURE FOR THIS LINK THUMBNAIL.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            reply_markup=cancel_kb
        )
        raise StopPropagation

    if data == "sl_cancel":
        _PENDING.pop(key, None)
        try:
            await query.answer("Process cancelled.")
        except Exception:
            pass
        await query.message.edit_text("❌ <b>Link generation cancelled.</b>")
        raise StopPropagation


async def capture_single(client, message):
    key = (client.me.id, message.from_user.id)
    if key not in _PENDING:
        return

    # CRITICAL: Custom Batch owns forwarded messages while its session is active.
    if _batch_active(client, message.from_user.id):
        _PENDING.pop(key, None)
        return

    raw_text = (message.text or message.caption or "").strip()
    if raw_text.lower() == "/cancel":
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
            
            # Clean previous prompt and the photo message
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

    # Delete prompt message above for clean chat
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
        "custom_thumbnail": thumb,
        "custom_thumb_path": thumb_path,
    }
    # Index under all possible token representations
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
    await message.reply(
        "⚡ <b>HERE IS YOUR LINK :</b>\n\n"
        f"🔗 {link}",
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
    v_text = None
    access_markup = None
    free_notice = None
    if isinstance(access_res, (tuple, list)):
        v_text = access_res[0]
        access_markup = access_res[1] if len(access_res) > 1 else None
        free_notice = access_res[3] if len(access_res) > 3 else None
    elif access_res:
        v_text, access_markup = "<b>🔐 Please verify first to access this file.</b>", access_res
    if access_markup:
        await message.reply(v_text, reply_markup=access_markup, disable_web_page_preview=True)
        raise StopPropagation
    if await send_fsub_prompt(client, message, payload):
        raise StopPropagation
    try:
        rec = bot_record(client)
        is_protect = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
        
        # Determine buttons
        custom_btns = rec.get("custom_buttons", [])
        markup = None
        if custom_btns:
            rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
            if rows:
                markup = InlineKeyboardMarkup(rows)

        source_chat = int(record["source_chat_id"])
        source_mid = int(record["source_message_id"])

        # Determine caption
        custom_cap = rec.get("custom_caption")
        invert_cap = bool(rec.get("invert_caption", False))
        spoiler_anim = bool(rec.get("spoiler_animation", False))
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(source_chat, source_mid)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        # Check thumbnail: Per-link thumbnail takes precedence over bot settings thumbnail
        thumb_to_use = (
            record.get("single_thumbnail_path")
            or record.get("single_thumbnail")
            or record.get("custom_thumb_path")
            or record.get("custom_thumbnail")
            or rec.get("custom_thumb_path")
            or rec.get("custom_thumbnail")
        )

        delivered = None
        if thumb_to_use:
            try:
                src_msg = await client.get_messages(source_chat, source_mid)
                thumb_path = await get_cached_thumb_path(client, thumb_to_use)
                
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
                        # Try send_video first for video documents (MKV, MP4, etc.)
                        send_kw_v = {
                            "chat_id": message.from_user.id,
                            "video": src_msg.document.file_id,
                            "caption": caption_to_use,
                            "thumb": thumb_path,
                            "supports_streaming": True,
                            "reply_markup": markup,
                            "protect_content": is_protect,
                        }
                        if caption_to_use:
                            send_kw_v["parse_mode"] = enums.ParseMode.HTML
                        if invert_cap:
                            send_kw_v["show_caption_above_media"] = True
                        if spoiler_anim:
                            send_kw_v["has_spoiler"] = True
                        try:
                            delivered = await client.send_video(**send_kw_v)
                        except Exception:
                            pass
                        
                        if not delivered:
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

            # 1. Full with invert_media + has_spoiler (Pyrofork standard)
            kw1 = dict(base_kw)
            if invert_cap:
                kw1["invert_media"] = True
            if spoiler_anim:
                kw1["has_spoiler"] = True
            attempts.append(kw1)

            # 2. Full with show_caption_above_media + has_spoiler (Pyrogram standard)
            if invert_cap or spoiler_anim:
                kw2 = dict(base_kw)
                if invert_cap:
                    kw2["show_caption_above_media"] = True
                if spoiler_anim:
                    kw2["has_spoiler"] = True
                attempts.append(kw2)

            # 3. Only has_spoiler
            if spoiler_anim:
                attempts.append({**base_kw, "has_spoiler": True})

            # 4. Base without extra flags
            attempts.append(base_kw)

            # 5. Fallback without parse_mode if custom tags failed
            fb_no_pm = dict(base_kw)
            fb_no_pm.pop("parse_mode", None)
            attempts.append(fb_no_pm)

            for attempt_kw in attempts:
                try:
                    delivered = await client.copy_message(**attempt_kw)
                    if delivered:
                        break
                except Exception:
                    continue

        if rec.get("auto_delete_enabled", True):
            ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 15)) * 60))
            time_str = format_auto_delete_time(ad_sec)
            u_mention = getattr(message.from_user, "mention", message.from_user.first_name)
            
            raw_ad_text = rec.get("auto_delete_text") or (
                "<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\n"
                "This Movie File/Video will be deleted in <b><u>{time}</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n"
                "<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
            )
            ad_text = raw_ad_text.replace("{time}", time_str).replace("{user_mention}", u_mention)

            # Build custom buttons if any
            ad_btns_cfg = rec.get("auto_delete_buttons", [])
            ad_rows = []
            for r_item in ad_btns_cfg:
                row_b = []
                if isinstance(r_item, dict) and "buttons" in r_item:
                    for b in r_item["buttons"]:
                        row_b.append(InlineKeyboardButton(b["text"], url=b["url"]))
                elif isinstance(r_item, dict) and "text" in r_item:
                    row_b.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
                elif isinstance(r_item, list):
                    for b in r_item:
                        if isinstance(b, dict) and b.get("text"):
                            row_b.append(InlineKeyboardButton(b["text"], url=b.get("url", "https://t.me")))
                if row_b:
                    ad_rows.append(row_b)
            ad_markup = InlineKeyboardMarkup(ad_rows) if ad_rows else None

            ad_pic = rec.get("auto_delete_pic")
            ad_spoil = bool(rec.get("auto_delete_pic_spoiler", False))
            ad_invert = bool(rec.get("auto_delete_pic_invert_caption", False))

            warning = None
            if ad_pic:
                try:
                    warning = await client.send_photo(
                        chat_id=message.from_user.id,
                        photo=ad_pic,
                        caption=ad_text,
                        has_spoiler=ad_spoil,
                        show_caption_above_media=ad_invert,
                        reply_markup=ad_markup
                    )
                except Exception:
                    pass
            if not warning:
                try:
                    warning = await client.send_message(
                        chat_id=message.from_user.id,
                        text=ad_text,
                        reply_markup=ad_markup
                    )
                except Exception:
                    pass

            if warning and delivered:
                try:
                    from link_modules.auto_delete_delivery import schedule_auto_delete
                    await schedule_auto_delete(client, message.from_user.id, [delivered.id, warning.id], ad_sec)
                except Exception:
                    async def _auto_del_task():
                        await asyncio.sleep(ad_sec)
                        try:
                            await client.delete_messages(chat_id=message.from_user.id, message_ids=[delivered.id, warning.id])
                        except Exception:
                            pass
                    asyncio.create_task(_auto_del_task())

            if free_notice and delivered:
                try:
                    await client.send_message(message.from_user.id, free_notice)
                except Exception:
                    pass

    except Exception:
        pass
    raise StopPropagation


def register(client, base_group=-100):
    private = filters.private
    client.add_handler(MessageHandler(genlink_prompt, filters.command(["link", "getlink", "genlink"]) & private), group=base_group)
    client.add_handler(MessageHandler(capture_single, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(single_link_callback, filters.regex(r"^sl_")), group=base_group)
    return client
