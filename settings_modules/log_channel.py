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
        prompt_msg = await edit_or_reply_fn(
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

            # Clean up prompt message from above so everything moves to bottom
            try:
                if prompt_msg:
                    await prompt_msg.delete()
                elif getattr(query, "message", None):
                    await query.message.delete()
            except Exception:
                pass

            if not fwd or fwd.text == "/cancel":
                clear_user_session(user_id)
                return await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
                )
            
            fwd_chat = getattr(fwd, "forward_from_chat", None)
            if not fwd_chat:
                clear_user_session(user_id)
                return await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Must forward a message from your log channel.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
                )

            # Check and announce Live connection to the log channel
            try:
                user_obj = await client.get_users(user_id)
                u_mention = user_obj.mention if user_obj else f"<code>{user_id}</code>"
                u_name = f"@{user_obj.username}" if getattr(user_obj, "username", None) else getattr(user_obj, "first_name", str(user_id))
            except Exception:
                u_mention = f"<code>{user_id}</code>"
                u_name = f"<code>{user_id}</code>"

            live_text = (
                f"🤖 <b>@{me.username} IS LIVE ✅</b>\n\n"
                f"👤 <b>Connected By:</b> {u_mention} ({u_name})\n"
                f"🆔 <b>Owner ID:</b> <code>{user_id}</code>\n"
                f"📢 <b>Log Channel:</b> {fwd_chat.title}"
            )

            try:
                await client.send_message(chat_id=fwd_chat.id, text=live_text)
            except Exception:
                clear_user_session(user_id)
                return await client.send_message(
                    chat_id=user_id,
                    text=f"❌ <b>Sorry, your bot is not admin this chnaal.</b>\n\n<i>Make sure @{me.username} is admin in your channel with all permissions and try again.</i>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
                )

            save_fn(log_channel=fwd_chat.id, log_channel_title=fwd_chat.title)
            r["log_channel"] = fwd_chat.id
            r["log_channel_title"] = fwd_chat.title
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
        r["log_channel"] = None
        r["log_channel_title"] = None
        await query.answer("Log channel deleted!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY DELETED LOG CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="log_channel")]])
        )


