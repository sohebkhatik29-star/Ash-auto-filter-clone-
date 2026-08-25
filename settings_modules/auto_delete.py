# ♻️ AUTO DELETE SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from clone_plugins.users_api import parse_auto_delete_time, format_auto_delete_time

async def handle_auto_delete_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("master_auto_delete_menu", "cset_autodelete", "cset_auto_delete_menu"):
        ad_on = bool(r.get("auto_delete_enabled", False))
        ad_time = int(r.get("auto_delete_time", 600))
        status_txt = "ON ✅" if ad_on else "OFF ❌"
        time_txt = format_auto_delete_time(ad_time)
        text = (
            "♻️ <b>MESSAGE AUTO DELETE:</b>\n\n"
            "<b>MESSAGE AUTO DELETE: IF TIME IS SET THEN BOT AUTOMATICALLY DELETE THE GIVEN MESSAGE. THIS WILL PREVENT BOT FROM GETTING BAN OR COPYRIGHT.</b>\n\n"
            f"<b>AUTO DELETE - {status_txt}</b>\n\n"
            f"<b>DELETE TIME - {time_txt.upper()}</b>"
        )
        tgl_btn = "OFF AUTO DELETE" if ad_on else "ON AUTO DELETE"
        back_cb = "settings" if data.startswith("master") else "cset_settings"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TIME", callback_data="cset_set_ad_time" if not data.startswith("master") else "m_set_ad_custom")],
            [InlineKeyboardButton(tgl_btn, callback_data="cset_tgl_ad" if not data.startswith("master") else "m_tgl_ad")],
            [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
        ]))

    if data in ("m_tgl_ad", "cset_tgl_ad", "cset_autodelete_toggle"):
        new_s = not bool(r.get("auto_delete_enabled", False))
        save_fn(auto_delete_enabled=new_s)
        await query.answer(f"Auto delete {'Enabled' if new_s else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu" if data.startswith("m_") else "cset_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_set_ad_custom", "cset_set_ad_time"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_ad_time")
        await query.answer()
        await query.message.reply(
            "<b>SEND ME A TIME IN LIKE THIS - 5s, 1m, 1h or 1d</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
        )
        async def _ad_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t_txt = (ans.text or "").strip()
            if t_txt == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            sec = parse_auto_delete_time(t_txt)
            if not sec or sec <= 0:
                await client.send_message(user_id, "❌ <b>Invalid time format. Example: 5s, 10s, 1m, 2h, 1d.</b>")
                clear_user_session(user_id)
                return
            save_fn(auto_delete_enabled=True, auto_delete_time=sec, auto_delete_minutes=max(1, sec // 60))
            clear_user_session(user_id)
            time_str = format_auto_delete_time(sec)
            menu_cb = "master_auto_delete_menu" if data.startswith("m_") else "cset_auto_delete_menu"
            await client.send_message(
                user_id,
                f"🧭 <b>SUCCESSFULLY SET DELETE TIME - {time_str}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]])
            )
        asyncio.create_task(_ad_worker())
        return

    if data.startswith("m_set_ad:") or data.startswith("cset_autodelete_set:") or data.startswith("cset_set_ad:"):
        sec = int(data.split(":")[1])
        save_fn(auto_delete_enabled=True, auto_delete_time=sec, auto_delete_minutes=max(1, sec // 60))
        time_str = format_auto_delete_time(sec)
        await query.answer(f"Auto delete set to {time_str}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu" if data.startswith("m_") else "cset_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

