# 🚫 DELETE BOT SETTINGS MODULE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def handle_delete_bot_callbacks(client, query, data, user_id, r, save_fn, db_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data == "cset_delete_bot":
        return await edit_or_reply_fn(
            query,
            "⚠️ <b>ARE YOU SURE YOU WANT TO DELETE THIS CLONE BOT?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ YES, DELETE", callback_data="cset_confirm_del_bot")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_confirm_del_bot":
        m = db_fn()
        if m:
            m.bots.delete_one({"bot_id": me.id})
            try:
                m.clone_settings.delete_many({"bot_id": me.id})
                m.free_usage.delete_many({"bot_id": me.id})
                m.access_tokens.delete_many({"bot_id": me.id})
                m.join_requests.delete_many({"bot_id": me.id})
            except Exception:
                pass
        try:
            import asyncio
            from plugins.clone import CLONES
            CLONES.pop(me.id, None)
            CLONES.pop(str(me.id), None)
            asyncio.create_task(client.stop())
        except Exception:
            pass
        await query.answer("Clone bot deleted!", show_alert=True)
        return await edit_or_reply_fn(query, "🚫 <b>Clone Bot Deleted Successfully.</b>")
