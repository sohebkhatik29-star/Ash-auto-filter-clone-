# 🔒 PROTECT CONTENT SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_protect_content_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings"
    tgl_cb = f"m_tgl_protect:{target_bid}" if target_bid else "m_tgl_protect"

    if data_str.startswith(("protect_menu", "master_protect_content", "cset_protect")) and not data_str.startswith(("cset_protect_toggle", "cset_tgl_protect")):
        protect = bool(r.get("protect_content", False))
        status_str = "ENABLE ✅" if protect else "DISABLE ❌"
        tgl_btn_text = "DISABLE ❌" if protect else "ENABLE ✅"

        text = (
            "🔒 <b>PROTECT CONTENT:</b>\n\n"
            "<blockquote>RESTRICT OTHER USERS FROM FORWARDING CONTENTS OF THIS BOT.</blockquote>\n\n"
            "<b>AVAILABLE MODES:</b>\n\n"
            "<b>- ENABLE: FORWARDING IS BLOCKED USERS CANNOT FORWARD ANY MESSAGE FROM BOT.</b>\n\n"
            "<b>- DISABLE: FORWARDING IS ALLOWED USERS CAN FORWARD MESSAGE FROM BOT.</b>\n\n"
            f"<b>FORWARD MODE - {status_str}</b>"
        )

        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tgl_btn_text, callback_data=tgl_cb)],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    if data_str.startswith(("m_tgl_protect", "cset_protect_toggle", "cset_tgl_protect", "protect_toggle", "protect_on", "protect_off")):
        if data_str.startswith("protect_on"):
            protect = True
        elif data_str.startswith("protect_off"):
            protect = False
        else:
            protect = not bool(r.get("protect_content", False))

        save_fn(protect_content=protect)
        r["protect_content"] = protect
        await query.answer(f"Forward Mode set to {'ENABLE' if protect else 'DISABLE'}!")
        return await handle_protect_content_callbacks(
            client, query, f"protect_menu:{target_bid}" if target_bid else "protect_menu",
            user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid
        )
