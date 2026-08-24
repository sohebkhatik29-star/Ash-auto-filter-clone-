# 🖼️ CUSTOM THUMBNAIL SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_thumbnail_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("custom_thumbnail", "cset_thumbnail"):
        thumb = r.get("custom_thumbnail")
        status_txt = "Configured ✅" if thumb else "Not Set ❌"
        text = f"🖼️ <b>CUSTOM THUMBNAIL:</b>\n\n<b>Status:</b> {status_txt}"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET THUMBNAIL", callback_data="m_set_thumb")],
            [InlineKeyboardButton("DELETE THUMBNAIL", callback_data="m_del_thumb")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_del_thumb", "cset_del_thumb"):
        save_fn(custom_thumbnail=None)
        await query.answer("Thumbnail removed!")
        return await handle_thumbnail_callbacks(client, query, "custom_thumbnail", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_set_thumb", "cset_set_thumb"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_thumb")
        await query.answer()
        await query.message.reply("🖼️ <b>Send a photo to set as Custom Thumbnail:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _thumb_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if ans.photo:
                save_fn(custom_thumbnail=ans.photo.file_id)
                clear_user_session(user_id)
                await client.send_message(user_id, "✅ <b>Custom Thumbnail saved!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="custom_thumbnail")]]))
            else:
                await client.send_message(user_id, "❌ <b>Please send a photo!</b>")
                clear_user_session(user_id)
        asyncio.create_task(_thumb_worker())
        return
