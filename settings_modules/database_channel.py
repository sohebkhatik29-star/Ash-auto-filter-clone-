# ☁️ DATABASE CHANNEL SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_database_channel_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data == "database_channel":
        db_ch = r.get("db_channel")
        db_title = r.get("db_channel_title")
        status_txt = f"<b>YOUR DATABASE CHANNEL - {db_title or db_ch}</b>" if db_ch else "<b>YOU DIDN'T ADDED ANY DATABASE CHANNEL ❗</b>"
        text = (
            "☁️ <b>DATABASE CHANNEL:</b>\n\n"
            "<b>WHAT IS DATABASE CHANNEL ?</b>\n\n"
            "<b>DATABASE CHANNEL MEANS WHEN YOU STORE ANYTHING IN FILE STORE BOT ALL MESSAGES BOT WILL STORE IN YOUR DATABASE CHANNEL. IF YOU DELETE THAT MESSAGE THEN BOT CAN NOT GIVE IT TO ANYONE.</b>\n\n"
            f"{status_txt}"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CHANNEL", callback_data="cset_set_db_ch"), InlineKeyboardButton("DELETE CHANNEL", callback_data="cset_del_db_ch")],
                [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_set_db_ch":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_db_ch")
        await query.answer()
        await edit_or_reply_fn(
            query,
            f"<b>FORWARD DATABASE CHANNEL ANY MESSAGE TO ME, AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="database_channel")]])
        )
        async def _db_worker():
            try:
                fwd = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if not fwd or fwd.text == "/cancel":
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="database_channel")]]) )
            fwd_chat = getattr(fwd, "forward_from_chat", None)
            if not fwd_chat:
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="❌ <b>Must forward from a channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="database_channel")]]) )
            save_fn(db_channel=fwd_chat.id, db_channel_title=fwd_chat.title)
            clear_user_session(user_id)
            return await client.send_message(
                chat_id=user_id,
                text=f"⚡ <b>SUCCESSFULLY ADDED YOUR DATABASE CHANNEL - {fwd_chat.title}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="database_channel")]])
            )
        asyncio.create_task(_db_worker())
        return

    if data == "cset_del_db_ch":
        save_fn(db_channel=None, db_channel_title=None)
        await query.answer("Database channel deleted!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY DELETED DATABASE CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="database_channel")]])
        )
