# 🖇️ LINK SHORTENER SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_shortener_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("link_shortener", "cset_shortener"):
        site = r.get("shortener_site") or "Not Set"
        api = r.get("shortener_api") or "Not Set"
        text = (
            "🖇️ <b>MAIN LINK SHORTNER:</b>\n\n"
            f"🌐 <b>DOMAIN / SITE:</b> <code>{site}</code>\n"
            f"🔑 <b>API KEY:</b> <code>{api}</code>\n\n"
            "<b>Connect your URL shortener service to earn from link generations.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET SHORTNER", callback_data="m_set_main_shortener")],
            [InlineKeyboardButton("DELETE SHORTNER", callback_data="m_del_main_shortener")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_del_main_shortener", "delete_shortener"):
        save_fn(shortener_site=None, shortener_api=None)
        await query.answer("Shortener removed!")
        return await handle_shortener_callbacks(client, query, "link_shortener", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_set_main_shortener", "add_shortener"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_main_short")
        await query.answer()
        await query.message.reply("🖇️ <b>Send your shortener website (e.g. <code>shareus.io</code>):</b>\n\n<i>Send /cancel to abort.</i>")
        async def _m_short_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            st = (ans.text or "").strip()
            if st == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            st = st.replace("http://", "").replace("https://", "").strip("/")
            await client.send_message(user_id, f"🔑 <b>Send your API key for <code>{st}</code>:</b>")
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            ap = (ans2.text or "").strip()
            if ap == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            save_fn(shortener_site=st, shortener_api=ap)
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>SHORTNER SAVED!</b>\n\n🌐 <b>Site:</b> <code>{st}</code>\n🔑 <b>API:</b> <code>{ap}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="link_shortener")]])
            )
        asyncio.create_task(_m_short_worker())
        return
