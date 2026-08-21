# 📢 FORCE SUBSCRIBE SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_fsub_callbacks(client, query, data, user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("master_fsub_menu", "cset_fsub_menu"):
        fsub_on = bool(r.get("fsub_enabled", False))
        ch_list = r.get("fsub_channels", [])
        status_txt = "ON ✅" if fsub_on else "OFF ❌"
        ch_text = "\n".join([f"• <code>{c}</code>" for c in ch_list]) if ch_list else "<i>No channels added yet.</i>"
        text = (
            "📢 <b>FORCE SUBSCRIBE SETTINGS:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n\n"
            f"<b>CONFIGURED CHANNELS:</b>\n{ch_text}\n\n"
            "<b>Users must join these channels before getting files.</b>"
        )
        tgl_btn = "DISABLE FORCE SUB" if fsub_on else "ENABLE FORCE SUB"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_fsub")],
            [InlineKeyboardButton("ADD FSUB CHANNEL", callback_data="m_add_fsub"), InlineKeyboardButton("CLEAR CHANNELS", callback_data="m_clear_fsub")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data in ("m_tgl_fsub", "cset_fsub_toggle"):
        new_s = not bool(r.get("fsub_enabled", False))
        save_fn(fsub_enabled=new_s)
        await query.answer(f"Force Sub {'Enabled' if new_s else 'Disabled'}!")
        return await handle_fsub_callbacks(client, query, "master_fsub_menu", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_clear_fsub", "cset_fsub_clear"):
        save_fn(fsub_channels=[])
        await query.answer("All FSub channels removed!")
        return await handle_fsub_callbacks(client, query, "master_fsub_menu", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_add_fsub", "cset_fsub_add"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_fsub_add")
        await query.answer()
        await query.message.reply("📢 <b>Forward a message from your channel or send Channel ID / Username:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _fsub_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            ch_val = None
            if ans.forward_from_chat:
                ch_val = ans.forward_from_chat.id
            elif txt:
                ch_val = int(txt) if txt.lstrip("-").isdigit() else txt
            if not ch_val:
                await client.send_message(user_id, "❌ <b>Invalid channel input.</b>")
                clear_user_session(user_id)
                return
            chs = get_rec_fn().get("fsub_channels", [])
            if ch_val not in chs:
                chs.append(ch_val)
            save_fn(fsub_channels=chs, fsub_enabled=True)
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>Channel added to Force Subscribe:</b> <code>{ch_val}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_fsub_menu")]])
            )
        asyncio.create_task(_fsub_worker())
        return
