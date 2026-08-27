# ♾️ PERMANENT LINK SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_permanent_link_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("master_permanent_link", "cset_permlink"):
        perm_on = bool(r.get("permanent_link_enabled", True))
        status_txt = "ON ✅" if perm_on else "OFF ❌"
        tgl_btn = "DISABLE PERMANENT LINK" if perm_on else "ENABLE PERMANENT LINK"
        text = (
            "♾️ <b>PERMANENT LINK:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n\n"
            "<b>When enabled, generated file links do not expire.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_perm")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_tgl_perm", "cset_permlink_toggle"):
        new_s = not bool(r.get("permanent_link_enabled", True))
        save_fn(permanent_link_enabled=new_s)
        await query.answer(f"Permanent links {'Enabled' if new_s else 'Disabled'}!")
        return await handle_permanent_link_callbacks(client, query, "master_permanent_link", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
