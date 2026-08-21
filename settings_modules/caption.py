# 🍿 CUSTOM CAPTION SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_caption_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("custom_caption", "cset_caption"):
        cap = r.get("custom_caption") or "Default Caption"
        text = (
            "🍿 <b>CUSTOM CAPTION:</b>\n\n"
            f"<b>CURRENT CAPTION:</b>\n<code>{cap}</code>\n\n"
            "<b>Variables available:</b>\n"
            "• <code>{filename}</code> - File Name\n"
            "• <code>{size}</code> - File Size"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET CUSTOM CAPTION", callback_data="m_set_caption")],
            [InlineKeyboardButton("RESET TO DEFAULT", callback_data="m_del_caption")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_del_caption", "caption_delete"):
        save_fn(custom_caption=None)
        await query.answer("Caption reset to default!")
        return await handle_caption_callbacks(client, query, "custom_caption", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_set_caption", "caption_edit"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_caption")
        await query.answer()
        await query.message.reply("🍿 <b>Send your new Custom Caption:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _cap_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t = (ans.text or "").strip()
            if t == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            save_fn(custom_caption=t)
            clear_user_session(user_id)
            await client.send_message(user_id, "✅ <b>Custom Caption updated!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="custom_caption")]]))
        asyncio.create_task(_cap_worker())
        return
