"""Universal Link generator handler.
Main command: /universal_link
"""
import secrets
import time
import asyncio
from pyrogram import StopPropagation, filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins.commands import bot_record, is_owner_or_mod, make_file_link
from plugins.clone import mongo_db
from config import ADMINS, PUBLIC_FILE_STORE
from clone_plugins.users_api import format_caption

_ACTIVE_UNIV_DELIVERIES = {}

def is_allowed_universal(client, user_id: int) -> bool:
    from clone_plugins.auth import is_clone_authorized
    return is_clone_authorized(client, user_id)

async def universal_link_cmd(client, message):
    if not is_allowed_universal(client, message.from_user.id):
        from clone_plugins.auth import UNAUTHORIZED_MESSAGE_TEXT, unauthorized_markup
        return await message.reply(UNAUTHORIZED_MESSAGE_TEXT, reply_markup=unauthorized_markup(client), disable_web_page_preview=True)
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    session_id = secrets.token_urlsafe(10)
    text = (
        "<b>Send the Inventory channel message link where the bot should start storing messages</b>\n\n"
        "<i>Note: This bot and any other clones that need to work with this link must have admin access to the channel at all times.</i>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"ul_cancel_{session_id}")]
    ])
    
    # Pehle message send karo taki uski ID mil sake
    sent_msg = await message.reply(text, reply_markup=markup, disable_web_page_preview=True)

    doc = {
        "session_id": session_id,
        "bot_id": client.me.id,
        "user_id": int(message.from_user.id),
        "step": "waiting_start",  # waiting_start -> waiting_stop
        "start_chat_id": None,
        "start_msg_id": None,
        "prompt_msg_id": sent_msg.id, # Puraney message ki ID yaha save ho rahi hai
        "created_at": int(time.time()),
    }
    
    mongo_db.universal_sessions.update_one(
        {"bot_id": client.me.id, "user_id": int(message.from_user.id)},
        {"$set": doc},
        upsert=True
    )
    raise StopPropagation

async def capture_universal_flow(client, message):
    if mongo_db is None or not message.from_user or not message.chat:
        return
    if message.chat.type.value != "private":
        return
    if message.text and message.text.startswith("/"):
        return

    session = mongo_db.universal_sessions.find_one({"bot_id": client.me.id, "user_id": int(message.from_user.id)})
    if not session:
        return

    step = session.get("step")
    prompt_msg_id = session.get("prompt_msg_id")

    # Helper function to check if bot is admin in the source chat/channel
    async def check_bot_admin(chat_id):
        try:
            member = await client.get_chat_member(chat_id, client.me.id)
            if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return True
        except Exception:
            pass
        return False

    # Handling Forwarded Message or direct link parsing
    chat_id = None
    msg_id = None

    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
    elif message.text and "t.me/" in message.text:
        # Basic link parser
        try:
            parts = message.text.strip().split("/")
            if "c" in parts:
                c_idx = parts.index("c")
                chat_id = int("-100" + parts[c_idx + 1])
                msg_id = int(parts[-1])
            else:
                username = parts[-2]
                msg_id = int(parts[-1])
                chat = await client.get_chat(username)
                chat_id = chat.id
        except Exception:
            pass

    if not chat_id or not msg_id:
        return await message.reply("❌ Please forward a message from the channel or send a valid channel message link.")

    # Check Admin Status
    is_admin = await check_bot_admin(chat_id)
    if not is_admin:
        if prompt_msg_id:
            try:
                await client.delete_messages(message.chat.id, prompt_msg_id)
            except Exception:
                pass
        mongo_db.universal_sessions.delete_one({"_id": session["_id"]})
        return await message.reply("❌ Sorry, your bot is not an admin in this channel. Please promote the bot as admin first.")

    if step == "waiting_start":
        # Purana 'start' wala message delete kar rahe hai
        if prompt_msg_id:
            try:
                await client.delete_messages(message.chat.id, prompt_msg_id)
            except Exception:
                pass

        text = "<b>Send the Inventory channel message link where the bot should stop storing messages</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"ul_cancel_{session['session_id']}")]
        ])
        
        # Naya message send karke uski ID update karenge
        sent_msg = await message.reply(text, reply_markup=markup, disable_web_page_preview=True)
        
        mongo_db.universal_sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {
                "start_chat_id": chat_id, 
                "start_msg_id": msg_id, 
                "step": "waiting_stop", 
                "prompt_msg_id": sent_msg.id
            }}
        )
        raise StopPropagation

    elif step == "waiting_stop":
        # Purana 'stop' wala message delete kar rahe hai
        if prompt_msg_id:
            try:
                await client.delete_messages(message.chat.id, prompt_msg_id)
            except Exception:
                pass

        start_chat_id = session.get("start_chat_id")
        start_msg_id = session.get("start_msg_id")
        stop_chat_id = chat_id
        stop_msg_id = msg_id

        if start_chat_id != stop_chat_id:
            return await message.reply("❌ Start and stop messages must be from the same channel!")

        if start_msg_id > stop_msg_id:
            return await message.reply("❌ Stop message ID must be greater than or equal to the start message ID!")

        # Processing shuru karte waqt message bhejenge
        proc_msg = await message.reply("⏳ <b>Processing files, please wait...</b>")
        messages_list = []
        
        rec = bot_record(client)
        protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
        username = (await client.get_me()).username

        for m_id in range(start_msg_id, stop_msg_id + 1):
            try:
                msg = await client.get_messages(start_chat_id, m_id)
                if msg and msg.media:
                    media = getattr(msg, msg.media.value, None)
                    file_id = getattr(media, "file_id", None)
                    if file_id:
                        messages_list.append({"chat_id": start_chat_id, "message_id": m_id})
            except Exception:
                continue

        if not messages_list:
            mongo_db.universal_sessions.delete_one({"_id": session["_id"]})
            await proc_msg.delete() # Processing wala message delete
            return await message.reply("❌ No valid media found in the given range.")

        # Save to database links collection
        token = secrets.token_urlsafe(18)
        doc_link = {
            "token": token,
            "bot_id": client.me.id,
            "owner_id": int(message.from_user.id),
            "messages": messages_list,
            "protected": protected,
            "created_at": int(time.time()),
        }
        mongo_db.custom_batch_links.update_one({"token": token}, {"$set": doc_link}, upsert=True)
        
        link = f"https://t.me/{username}?start=batch_{token}"
        mongo_db.universal_sessions.delete_one({"_id": session["_id"]})

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Copy Link 📋", url=f"https://t.me/share/url?url={link}"),
                InlineKeyboardButton("📢 SHARE URL 📢", url=f"https://t.me/share/url?url={link}")
            ]
        ])
        
        # Process complete hone ke baad "Processing..." message delete kar denge
        await proc_msg.delete()
        await message.reply(f"Here is your universal link:\n\n{link}", reply_markup=markup, disable_web_page_preview=True)
        raise StopPropagation

async def universal_callback(client, query):
    data = query.data or ""
    if data.startswith("ul_cancel_"):
        try:
            session_id = data.split("_", 2)[2]
            mongo_db.universal_sessions.delete_one({"session_id": session_id})
            await query.message.delete()
        except Exception:
            pass
        await query.answer("Cancelled successfully.")
    raise StopPropagation

async def deliver_universal_link(client, message, token: str):
    from settings_modules.active_deactive import check_clone_status_or_block
    if await check_clone_status_or_block(client, message):
        return
    if mongo_db is None:
        return await message.reply("❌ Database not configured.")
    clean_tok = token.split("_", 1)[1] if "_" in token else token
    raw_tok = token.strip()
    record = mongo_db.universal_links.find_one({"$or": [{"token": token}, {"token": raw_tok}, {"token": clean_tok}, {"token": clean_tok.strip()}]})
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
    try:
        rec = cmd.bot_record(client) if hasattr(cmd, "bot_record") else {}
    except Exception:
        rec = {}

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

def is_universal_link_active(bot_id: int, user_id: int) -> bool:
    session = mongo_db.universal_sessions.find_one({"bot_id": bot_id, "user_id": user_id})
    if session:
        return True
    return False

def register(client, base_group=-104):
    private = filters.private
    client.add_handler(MessageHandler(universal_link_cmd, filters.command(["universal_link"]) & private), group=base_group)
    client.add_handler(MessageHandler(capture_universal_flow, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(universal_callback, filters.regex(r"^ul_cancel_[A-Za-z0-9_-]+$")), group=base_group)
    client.add_handler(CallbackQueryHandler(callback_cancel, filters.regex(r"^univ_cancel_")), group=base_group)
    return client

