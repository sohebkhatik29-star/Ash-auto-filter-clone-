# 🔄 RESTART BOT SETTINGS MODULE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_restart_bot_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data == "cset_restart_bot":
        await query.answer("Restarting bot...", show_alert=True)
        log_ch = r.get("log_channel")
        if log_ch:
            try:
                await client.send_message(
                    chat_id=int(log_ch),
                    text=f"🤖 @{me.username} IS RESTARTED ✅"
                )
            except Exception:
                pass
        return await edit_or_reply_fn(
            query,
            f"🔄 <b>@{me.username} is restarting...</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]])
        )

