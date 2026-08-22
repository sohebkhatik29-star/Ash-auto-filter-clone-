# ♻️ AUTO DELETE SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_auto_delete_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("master_auto_delete_menu", "cset_autodelete"):
        ad_on = bool(r.get("auto_delete_enabled", False))
        ad_time = r.get("auto_delete_time", 600)
        status_txt = f"ON ({ad_time // 60} Mins) ✅" if ad_on else "OFF ❌"
        text = (
            "♻️ <b>AUTO DELETE MESSAGES:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n\n"
            "<b>Automatically delete delivered files after a given time to protect copyright.</b>"
        )
        tgl_btn = "DISABLE AUTO DELETE" if ad_on else "ENABLE AUTO DELETE"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_ad")],
            [InlineKeyboardButton("SET TIME (10 MINS)", callback_data="m_set_ad:600"), InlineKeyboardButton("SET TIME (30 MINS)", callback_data="m_set_ad:1800")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_tgl_ad", "cset_autodelete_toggle"):
        new_s = not bool(r.get("auto_delete_enabled", False))
        save_fn(auto_delete_enabled=new_s)
        await query.answer(f"Auto delete {'Enabled' if new_s else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data.startswith("m_set_ad:") or data.startswith("cset_autodelete_set:"):
        sec = int(data.split(":")[1])
        save_fn(auto_delete_enabled=True, auto_delete_time=sec)
        await query.answer(f"Auto delete set to {sec // 60} Minutes!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
