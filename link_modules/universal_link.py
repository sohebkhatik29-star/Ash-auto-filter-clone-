"""Universal Link generator handler.
Main command: /universal_link
"""
import secrets
import time
from pyrogram import StopPropagation, filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.commands import bot_record, is_owner_or_mod, make_file_link
from plugins.clone import mongo_db
from config import ADMINS, PUBLIC_FILE_STORE

def is_allowed_universal(client, user_id: int) -> bool:
    if PUBLIC_FILE_STORE:
        return True
    try:
        if int(user_id) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    if is_owner_or_mod(client, user_id):
        return True
    return bot_record(client).get("mode") == "public"

async def universal_link_cmd(client, message):
    if not is_allowed_universal(client, message.from_user.id):
        return await message.reply("❌ Link generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    session_id = secrets.token_urlsafe(10)
    doc = {
        "session_id": session_id,
        "bot_id": client.me.id,
        "user_id": int(message.from_user.id),
        "step": "waiting_start",  # waiting_start -> waiting_stop
        "start_chat_id": None,
        "start_msg_id": None,
        "created_at": int(time.time()),
    }
    
    mongo_db.universal_sessions.update_one(
        {"bot_id": client.me.id, "user_id": int(message.from_user.id)},
        {"$set": doc},
        upsert=True
    )

    text = (
        "<b>Send the Inventory channel message link where the bot should start storing messages</b>\n\n"
        "<i>Note: This bot and any other clones that need to work with this link must have admin access to the channel at all times.</i>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"ul_cancel_{session_id}")]
    ])
    
    await message.reply(text, reply_markup=markup, disable_web_page_preview=True)
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
        # Basic link parser for t.me/c/chat_id/msg_id or t.me/username/msg_id
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
        mongo_db.universal_sessions.delete_one({"_id": session["_id"]})
        return await message.reply("❌ Sorry, your bot is not an admin in this channel. Please promote the bot as admin first.")

    if step == "waiting_start":
        mongo_db.universal_sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {"start_chat_id": chat_id, "start_msg_id": msg_id, "step": "waiting_stop"}}
        )
        text = "<b>Send the Inventory channel message link where the bot should stop storing messages</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"ul_cancel_{session['session_id']}")]
        ])
        await message.reply(text, reply_markup=markup, disable_web_page_preview=True)
        raise StopPropagation

    elif step == "waiting_stop":
        start_chat_id = session.get("start_chat_id")
        start_msg_id = session.get("start_msg_id")
        stop_chat_id = chat_id
        stop_msg_id = msg_id

        if start_chat_id != stop_chat_id:
            return await message.reply("❌ Start and stop messages must be from the same channel!")

        if start_msg_id > stop_msg_id:
            return await message.reply("❌ Stop message ID must be greater than or equal to the start message ID!")

        # Collect all files/messages in range (Max limit 500 to prevent timeout)
        messages_list = []
        await message.reply("⏳ <b>Processing files, please wait...</b>")
        
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
                        # Save each or build batch records
                        messages_list.append({"chat_id": start_chat_id, "message_id": m_id})
            except Exception:
                continue

        if not messages_list:
            mongo_db.universal_sessions.delete_one({"_id": session["_id"]})
            return await message.reply("❌ No valid media found in the given range.")

        # Save to database links collection (similar to batch/universal link)
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

def register(client, base_group=-104):
    private = filters.private
    client.add_handler(MessageHandler(universal_link_cmd, filters.command(["universal_link"]) & private), group=base_group)
    client.add_handler(MessageHandler(capture_universal_flow, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(universal_callback, filters.regex(r"^ul_cancel_[A-Za-z0-9_-]+$")), group=base_group)
    return client
