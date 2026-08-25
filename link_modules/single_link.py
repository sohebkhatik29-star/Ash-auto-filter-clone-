"""Single file / media shareable link generator and delivery handler.
Main command in menus: /getlink
Aliases supported: /link, /genlink
"""
import base64
import secrets
import time
import asyncio

from pyrogram import StopPropagation, filters, enums
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins.users_api import get_user, get_short_link, format_caption, format_auto_delete_time
from plugins.clone import mongo_db
from clone_plugins.commands import bot_record, force_markup, access_verification, send_fsub_prompt

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
    _PENDING[(client.me.id, message.from_user.id)] = int(time.time())
    await message.reply(
        "<b>SEND ME YOUR MESSAGE WHICH YOU WANT TO STORE</b>\n\n"
        "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
    )
    raise StopPropagation


async def capture_single(client, message):
    key = (client.me.id, message.from_user.id)
    if key not in _PENDING:
        return

    # CRITICAL: Custom Batch owns forwarded messages while its session is active.
    if _batch_active(client, message.from_user.id):
        _PENDING.pop(key, None)
        return

    _PENDING.pop(key, None)
    if message.text and message.text.strip().lower() == "/cancel":
        await message.reply("❌ Cancelled.")
        raise StopPropagation
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
        "created_at": int(time.time())
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
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(source_chat, source_mid)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        try:
            delivered = await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=source_chat,
                message_id=source_mid,
                caption=caption_to_use,
                parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                reply_markup=markup,
                protect_content=is_protect,
            )
        except Exception:
            # If HTML parsing failed due to custom user tags, fallback without parse_mode
            delivered = await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=source_chat,
                message_id=source_mid,
                caption=caption_to_use,
                reply_markup=markup,
                protect_content=is_protect,
            )

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

            try:
                if ad_pic:
                    warning = await client.send_photo(
                        chat_id=message.from_user.id,
                        photo=ad_pic,
                        caption=ad_text,
                        has_spoiler=ad_spoil,
                        show_caption_above_media=ad_invert,
                        reply_markup=ad_markup
                    )
                else:
                    warning = await client.send_message(
                        chat_id=message.from_user.id,
                        text=ad_text,
                        reply_markup=ad_markup
                    )
            except Exception:
                warning = await client.send_message(
                    chat_id=message.from_user.id,
                    text=ad_text,
                    reply_markup=ad_markup
                )

            async def _auto_del():
                await asyncio.sleep(ad_sec)
                try:
                    await delivered.delete()
                except Exception:
                    pass

                get_again_on = bool(rec.get("auto_delete_get_again", True))
                if get_again_on:
                    try:
                        me = await client.get_me()
                        again_url = f"https://t.me/{me.username}?start={token}"
                        again_kb = InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ GET MESSAGE AGAIN ✅", url=again_url)],
                            [InlineKeyboardButton("🔒 CLOSE 🔒", callback_data="close_data")]
                        ])
                        del_txt = (
                            "🎁 <b>PREVIOUS MESSAGE IS DELETED</b>\n\n"
                            "<b>IF YOU WANT THIS PREVIOUS MESSAGE AGAIN THEN CLICK ON BELOW BUTTON OTHERWISE CLICK ON CLOSE BUTTON.</b>"
                        )
                        if warning:
                            try:
                                await warning.delete()
                            except Exception:
                                pass
                        await client.send_message(chat_id=message.from_user.id, text=del_txt, reply_markup=again_kb)
                    except Exception:
                        pass
                else:
                    try:
                        await warning.delete()
                    except Exception:
                        pass
            asyncio.create_task(_auto_del())

    except Exception as e:
        await message.reply("❌ Unable to deliver this message. The original message may no longer be available.")
    raise StopPropagation


def register(client, base_group=-100):
    private = filters.private
    client.add_handler(MessageHandler(genlink_prompt, filters.command(["getlink", "link", "genlink"]) & private), group=base_group)
    client.add_handler(MessageHandler(capture_single, private), group=base_group + 1)
    return client
