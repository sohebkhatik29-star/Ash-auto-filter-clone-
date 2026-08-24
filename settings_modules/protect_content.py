# 🔒 PROTECT CONTENT SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_protect_content_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("protect_menu", "master_protect_content", "cset_protect"):
        protect = bool(r.get("protect_content", False))
        status_txt = "ON ✅" if protect else "OFF ❌"
        tgl_btn = "OFF PROTECT CONTENT" if protect else "ON PROTECT CONTENT"
        text = (
            "🔒 <b>PROTECT CONTENT:</b>\n\n"
            "<b>PROTECT CONTENT: PREVENT USERS FROM FORWARDING AND SAVING MESSAGES SENT BY THIS BOT.</b>\n\n"
            f"<b>PROTECT CONTENT - {status_txt}</b>"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_protect")],
                [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
            ])
        )

    if data in ("m_tgl_protect", "cset_protect_toggle"):
        protect = not bool(r.get("protect_content", False))
        save_fn(protect_content=protect)
        await query.answer(f"Protect Content {'Enabled' if protect else 'Disabled'}!")
        return await handle_protect_content_callbacks(client, query, "protect_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
