"""Universal Link generator & delivery handler.
Matches exact clone bot specifications.
"""
import asyncio
import re
import secrets
import time
from pyrogram import StopPropagation, enums, filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
try:
    from plugins.clone import mongo_db
except Exception:
    try:
        from clone_plugins.database import mongo_db
    except Exception:
        mongo_db = None
from settings_modules.caption_formatter import format_caption


_UNIV_SESSIONS = {}
_ACTIVE_UNIV_DELIVERIES = {}


def _get_session_key(client, user_id):
    return (int(client.me.id), int(user_id))


def is_universal_link_active(bot_id: int, user_id: int) -> bool:
    return _UNIV_SESSIONS.get((int(bot_id), int(user_id))) is not None


def _parse_message_reference(message):
    """Extract chat_id and msg_id from a forwarded message or a Telegram link."""
    # 1. Forwarded message from a channel/chat
    f_chat = message.forward_from_chat
    if f_chat and getattr(message, "forward_from_message_id", None):
        return f_chat.id, int(message.forward_from_message_id)

    # 2. Text message containing a link
    text = (message.text or message.caption or "").strip()
    if text:
        # Match t.me/c/123456789/10
        m = re.search(r"t\.me/c/(\d+)/(\d+)", text)
        if m:
            raw_id = int(m.group(1))
            c_id = int(f"-100{raw_id}") if not str(raw_id).startswith("-100") else raw_id
            return c_id, int(m.group(2))

        # Match t.me/username/10
        m2 = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", text)
        if m2 and m2.group(1).lower() not in ("c", "share", "joinchat"):
            return m2.group(1), int(m2.group(2))

    return None, None


async def universal_link_cmd(client, message):
    from settings_modules.active_deactive import check_clone_status_or_block
    if await check_clone_status_or_block(client, message):
        return

    user_id = int(message.from_user.id)
    s_key = _get_session_key(client, user_id)
    _UNIV_SESSIONS[s_key] = {"step": "first", "first_chat_id": None, "first_msg_id": None}

    help_url = "https://t.me/Ash_Updates1"
    text = (
        "Send the Inventory channel message link where the bot should start storing messages\n\n"
        f"Note: This bot and any other clones that need to work with this link must have admin access to the channel at all times. <a href=\"{help_url}\">To know more click here</a>"
    )
    await message.reply(text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    raise StopPropagation


async def capture_universal_step(client, message):
    user_id = int(message.from_user.id)
    s_key = _get_session_key(client, user_id)
    session = _UNIV_SESSIONS.get(s_key)
    if not session:
        return

    text = (message.text or message.caption or "").strip()
    if text.lower() == "/cancel":
        _UNIV_SESSIONS.pop(s_key, None)
        await message.reply("❌ Universal link generation cancelled.")
        raise StopPropagation

    step = session.get("step")
    chat_id, msg_id = _parse_message_reference(message)

    if not chat_id or not msg_id:
        await message.reply(
            "Please forward a message from your Inventory channel (with forward tag) or send a valid message link.\n\n"
            "<i>Send /cancel to abort.</i>",
            parse_mode=enums.ParseMode.HTML
        )
        raise StopPropagation

    if step == "first":
        try:
            chat_obj = await client.get_chat(chat_id)
            chat_id = chat_obj.id
            bot_member = await client.get_chat_member(chat_id, client.me.id)
            if str(bot_member.status).lower().endswith(("left", "banned", "kicked")):
                raise PermissionError("Not an admin")
        except Exception:
            await message.reply("This may be a private channel / group. Make me an admin over there.")
            raise StopPropagation

        session["first_chat_id"] = chat_id
        session["first_msg_id"] = msg_id
        session["step"] = "last"

        await message.reply("Send the Inventory channel message link where the bot should stop storing messages")
        raise StopPropagation

    elif step == "last":
        try:
            chat_obj = await client.get_chat(chat_id)
            chat_id = chat_obj.id
            bot_member = await client.get_chat_member(chat_id, client.me.id)
            if str(bot_member.status).lower().endswith(("left", "banned", "kicked")):
                raise PermissionError("Not an admin")
        except Exception:
            await message.reply("This may be a private channel / group. Make me an admin over there.")
            raise StopPropagation

        first_chat_id = session.get("first_chat_id")
        if chat_id != first_chat_id:
            await message.reply(
                "❌ <b>Both messages must be from the same channel!</b>\n"
                "Please forward the last message from the same channel or send /cancel.",
                parse_mode=enums.ParseMode.HTML
            )
            raise StopPropagation

        f_id = int(session["first_msg_id"])
        l_id = int(msg_id)
        if f_id > l_id:
            f_id, l_id = l_id, f_id

        total_msgs = l_id - f_id + 1
        _UNIV_SESSIONS.pop(s_key, None)

        notice_msg = await message.reply("Please Wait ....")

        token = secrets.token_urlsafe(18)
        if mongo_db is not None:
            doc = {
                "token": token,
                "user_id": user_id,
                "channel_id": chat_id,
                "first_msg_id": f_id,
                "last_msg_id": l_id,
                "total_msgs": total_msgs,
                "created_at": time.time(),
            }
            mongo_db.universal_links.insert_one(doc)

        orig_link = f"https://t.me/{client.me.username}?start={token}"
        from settings_modules.link_shortener import get_shortened_link_if_enabled
        shown_link = await get_shortened_link_if_enabled(client, user_id, orig_link)

        try:
            await notice_msg.delete()
        except Exception:
            pass

        help_url = "https://t.me/Ash_Updates1"
        final_text = (
            "Here is your universal link:\n\n"
            f"{shown_link}\n\n"
            "Note:The same content can be accessed by any of your clones by replacing the bot username in the link. "
            f"The link creator (you) must be a moderator in those clones. <a href=\"{help_url}\">To know more click here</a>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 SHARE URL", url=f"https://t.me/share/url?url={shown_link}")]
        ])

        await message.reply(
            final_text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        raise StopPropagation


async def deliver_universal_link(client, message, token: str):
    from settings_modules.active_deactive import check_clone_status_or_block
    if await check_clone_status_or_block(client, message):
        return

    if mongo_db is None:
        return await message.reply("❌ Database not configured.")

    clean_tok = token.split("_", 1)[1] if "_" in token else token
    record = mongo_db.universal_links.find_one({"$or": [{"token": token}, {"token": clean_tok}]})
    if not record:
        return await message.reply("❌ <b>This link is invalid or expired!</b>", parse_mode=enums.ParseMode.HTML)

    user_id = int(message.from_user.id)
    payload = token

    # Check access/verification
    access_markup, v_text, v_photo, free_notice = None, None, None, None
    from clone_plugins.users_api import check_access_and_get_markup
    access_res = await check_access_and_get_markup(client, message, payload)
    if isinstance(access_res, tuple):
        access_markup = access_res[0]
        v_text = access_res[1]
        v_photo = access_res[2] if len(access_res) > 2 else None
        free_notice = access_res[3] if len(access_res) > 3 else None
    elif access_res:
        v_text, access_markup = "<b>🔐 Please verify first to access this link.</b>", access_res
    if access_markup:
        await cmd.send_verify_prompt(client, message, v_text, access_markup, v_photo)
        raise StopPropagation
    if await cmd.send_fsub_prompt(client, message, payload):
        raise StopPropagation

    delivery_key = (int(client.me.id), user_id)
    _ACTIVE_UNIV_DELIVERIES[delivery_key] = True

    from settings_modules.update_channel import send_wait_message
    wait_msg = await send_wait_message(client, message, cancel_callback_data=f"univ_cancel_{token}")

    f_id = int(record["first_msg_id"])
    l_id = int(record["last_msg_id"])
    ch_id = int(record["channel_id"])
    protected = bool(record.get("protected", False)) or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

    custom_btns = rec.get("custom_buttons", [])
    markup = None
    if custom_btns:
        rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
        if rows:
            markup = InlineKeyboardMarkup(rows)

    custom_cap = rec.get("custom_caption")
    invert_cap = bool(rec.get("invert_caption", False))
    spoiler_anim = bool(rec.get("spoiler_animation", False))

    delivered_messages = []
    for m_id in range(f_id, l_id + 1):
        if not _ACTIVE_UNIV_DELIVERIES.get(delivery_key, False):
            break
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(ch_id, m_id)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        base_kw = {
            "chat_id": user_id,
            "from_chat_id": ch_id,
            "message_id": m_id,
            "caption": caption_to_use,
            "reply_markup": markup,
            "protect_content": protected,
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

        delivered = None
        for attempt_kw in attempts:
            try:
                delivered = await client.copy_message(**attempt_kw)
                await asyncio.sleep(0.1)
                break
            except Exception:
                continue

        if delivered:
            delivered_messages.append(delivered)

    _ACTIVE_UNIV_DELIVERIES.pop(delivery_key, None)
    try:
        await wait_msg.delete()
    except Exception:
        pass

    try:
        ad_enabled = bool(rec.get("auto_delete_enabled", False))
        ad_sec = int(rec.get("auto_delete_time") or (int(rec.get("auto_delete_minutes", 0) or 0) * 60) or 0)
        if ad_enabled and ad_sec > 0 and delivered_messages:
            from link_modules.auto_delete_delivery import schedule_auto_delete
            await schedule_auto_delete(client, user_id, delivered_messages, ad_sec)
    except Exception:
        pass

    if free_notice and delivered_messages:
        try:
            await client.send_message(user_id, free_notice)
        except Exception:
            pass

    raise StopPropagation


async def callback_cancel(client, query):
    data = query.data or ""
    if not data.startswith("univ_cancel_"):
        return
    delivery_key = (int(client.me.id), int(query.from_user.id))
    _ACTIVE_UNIV_DELIVERIES[delivery_key] = False
    await query.answer("Delivery cancelled.")
    try:
        await query.message.delete()
    except Exception:
        pass
    raise StopPropagation


def register(client, base_group=-104):
    private = filters.private
    client.add_handler(MessageHandler(capture_universal_step, private), group=base_group - 1)
    client.add_handler(MessageHandler(universal_link_cmd, filters.command(["universal_link"]) & private), group=base_group)
    client.add_handler(CallbackQueryHandler(callback_cancel, filters.regex(r"^univ_cancel_")), group=base_group)
    return client
