# 📢 LOG CHANNEL SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_log_channel_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data == "log_channel":
        log_ch = r.get("log_channel")
        log_title = r.get("log_channel_title")
        status_txt = f"<b>YOUR LOG CHANNEL - {log_title or log_ch}</b>" if log_ch else "<b>YOU DIDN'T ADDED ANY LOG CHANNEL ❗</b>"
        text = (
            "📢 <b>LOG CHANNEL:</b>\n\n"
            "<b>WHAT IS LOG CHANNEL ??</b>\n"
            "<b>IF NEW USERS START YOUR CLONE BOT THEN BOT NOTIFIES YOU.</b>\n\n"
            f"{status_txt}"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CHANNEL", callback_data="cset_set_log"), InlineKeyboardButton("DELETE CHANNEL", callback_data="cset_del_log")],
                [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_set_log":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_log")
        await query.answer()
        await edit_or_reply_fn(
            query,
            f"<b>FORWARD LOG CHANNEL ANY MESSAGE TO ME,\nAND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
        )
        async def _log_worker():
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
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]]) )
            fwd_chat = getattr(fwd, "forward_from_chat", None)
            if not fwd_chat:
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="❌ <b>Must forward a message from your log channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]]) )
            
            save_fn(log_channel=fwd_chat.id, log_channel_title=fwd_chat.title)
            clear_user_session(user_id)
            return await client.send_message(
                chat_id=user_id,
                text=f"⚡️ <b>SUCCESSFULLY ADDED YOUR LOG CHANNEL - {fwd_chat.title}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
            )
        asyncio.create_task(_log_worker())
        return

    if data == "cset_del_log":
        save_fn(log_channel=None, log_channel_title=None)
        await query.answer("Log channel deleted!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY DELETED LOG CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
        )

