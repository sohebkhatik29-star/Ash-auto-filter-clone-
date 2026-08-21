"""Master-only forwarded BotFather token handler.

This handles the create-clone session on the real master client without
changing any other clone commands or features.
"""
import re
from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client

from config import API_ID, API_HASH
from clone_plugins.sessions import cancel_all_listeners, clear_user_session
from clone_plugins import master_manager


def _pending_create_clone(user_id):
    try:
        from clone_plugins.sessions import _USER_SESSIONS
        token = _USER_SESSIONS.get(int(user_id))
        return bool(token and str(token).startswith("create_clone:"))
    except Exception:
        return False


async def _handle_create_clone_message(client, message):
    user_id = int(message.from_user.id) if message.from_user else 0
    if not user_id or not _pending_create_clone(user_id):
        return

    text = (message.text or message.caption or "").strip()
    cancel_all_listeners(client, message.chat.id, user_id)

    if text.lower() == "/cancel":
        return await client.send_message(user_id, "<b>Cancelled 🚫</b>")

    match = re.search(r"\b(\d+:[A-Za-z0-9_-]+)\b", text)
    if not match:
        return await client.send_message(
            user_id,
            "<b>❌ Could not read the bot token. Please forward the BotFather token message again.</b>",
        )

    bot_token = match.group(1)
    clear_user_session(user_id)
    m = master_manager.db()

    if m is not None and m.bots.count_documents({"user_id": user_id}) >= master_manager.MAX_USER_CLONES:
        return await client.send_message(user_id, "❌ <b>You can create maximum 5 clone bots.</b>")

    msg = await client.send_message(user_id, "<b>👨‍💻 Creating your clone...</b>")
    try:
        from plugins.clone import register_clone_handlers, set_clone_menu

        bot_prefix = int(bot_token.split(":", 1)[0])
        vj = Client(
            f"clone_{user_id}_{bot_prefix}",
            API_ID,
            API_HASH,
            bot_token=bot_token,
            plugins={},
        )
        await vj.start()
        register_clone_handlers(vj)
        bot = await vj.get_me()

        if m is not None:
            m.bots.update_one(
                {"bot_id": bot.id},
                {"$set": {
                    "bot_id": bot.id,
                    "is_bot": True,
                    "user_id": user_id,
                    "name": bot.first_name,
                    "token": bot_token,
                    "username": bot.username,
                    "force_channels": [],
                    "custom_caption": None,
                    "custom_buttons": [],
                    "protect_content": False,
                    "no_forward": False,
                    "auto_delete_enabled": False,
                    "auto_delete_minutes": 15,
                    "access_token_enabled": False,
                    "access_token_hours": 1,
                    "moderators": [],
                    "mode": "private",
                    "deactivated": False,
                    "hide_owner": False,
                }},
                upsert=True,
            )

        await set_clone_menu(vj, user_id)
        await msg.edit_text(
            f"✨ <b>Successfully Cloned Your Bot: @{bot.username}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🤖 OPEN @{bot.username} ↗", url=f"https://t.me/{bot.username}")],
                [InlineKeyboardButton("‹ MY CLONE BOTS", callback_data="my_clones")],
            ]),
        )
    except Exception as e:
        await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>")


def register_master_clone_forward_handler(client):
    client.add_handler(
        MessageHandler(_handle_create_clone_message, filters.private),
        group=-99,
    )
