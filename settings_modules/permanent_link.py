# ♾️ PERMANENT LINK SETTINGS MODULE
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_permanent_link_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    try:
        await query.answer("🚧 Coming Soon!", show_alert=False)
    except Exception:
        pass

    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    back_cb = f"manage_clone:{target_bid}" if target_bid else ("clone_my_clone_info" if "cset" in data_str else "settings")

    text = (
        "♾️ <b>PERMANENT LINK:</b>\n\n"
        "🚧 <b>COMING SOON...</b>\n\n"
        "<i>This feature is currently under development and will be available soon!</i>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])
    return await edit_or_reply_fn(query, text, reply_markup=markup)
