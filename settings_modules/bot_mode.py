# 🎁 BOT MODE SETTINGS MODULE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_bot_mode_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, clone_hub_markup_fn):
    me = client.me
    if data == "cset_bot_mode":
        curr_mode = r.get("mode", "public")
        new_mode = "private" if curr_mode == "public" else "public"
        save_fn(mode=new_mode)
        await query.answer(f"Bot mode switched to {new_mode.upper()}!", show_alert=True)
        return await edit_or_reply_fn(query, f"🎁 <b>BOT MODE:</b> <b>{new_mode.upper()}</b>", reply_markup=clone_hub_markup_fn(me.username))
