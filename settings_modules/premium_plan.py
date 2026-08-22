# 💸 PREMIUM PLAN SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session, cancel_all_listeners

async def handle_premium_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data == "master_premium_plan" or data == "cset_premium_plan":
        prem_enabled = bool(r.get("premium_enabled", False))
        status_txt = "ON ✅" if prem_enabled else "OFF ❌"
        p_text = r.get("premium_plan_text") or "Default plans: 1 Month - ₹50 | 1 Year - ₹300"
        p_upi = r.get("premium_upi_id") or "Not Set"
        text = (
            "💸 <b>PREMIUM PLAN SETTINGS:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n"
            f"• <b>UPI ID:</b> <code>{p_upi}</code>\n"
            f"• <b>PLAN DESCRIPTION:</b>\n{p_text}\n\n"
            "<b>Use options below to customize your premium offerings.</b>"
        )
        tgl_label = "DISABLE PREMIUM" if prem_enabled else "ENABLE PREMIUM"
        back_cb = "settings"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_label, callback_data="m_prem_tgl")],
            [InlineKeyboardButton("SET PLAN TEXT", callback_data="m_set_prem_txt"), InlineKeyboardButton("SET UPI ID", callback_data="m_set_prem_upi")],
            [InlineKeyboardButton("SET PAYMENT QR/PHOTO", callback_data="m_set_prem_pic")],
            [InlineKeyboardButton("🪧 BACK", callback_data=back_cb)]
        ]))

    if data == "m_prem_tgl":
        new_s = not bool(r.get("premium_enabled", False))
        save_fn(premium_enabled=new_s)
        await query.answer(f"Premium plan {'Enabled' if new_s else 'Disabled'}!")
        return await handle_premium_callbacks(client, query, "master_premium_plan", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data == "m_set_prem_txt":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_txt")
        await query.answer()
        await query.message.reply("💸 <b>Send new Premium Plan description text:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _ptxt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t = (ans.text or "").strip()
            if t == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            save_fn(premium_plan_text=t)
            clear_user_session(user_id)
            await client.send_message(user_id, "✅ <b>Premium plan text updated!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_premium_plan")]]))
        asyncio.create_task(_ptxt_worker())
        return

    if data == "m_set_prem_upi":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_upi")
        await query.answer()
        await query.message.reply("💸 <b>Send your UPI ID (e.g. <code>example@okaxis</code>):</b>\n\n<i>Send /cancel to abort.</i>")
        async def _pupi_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            u = (ans.text or "").strip()
            if u == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            save_fn(premium_upi_id=u)
            clear_user_session(user_id)
            await client.send_message(user_id, f"✅ <b>UPI ID set to:</b> <code>{u}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_premium_plan")]]))
        asyncio.create_task(_pupi_worker())
        return

    if data == "m_set_prem_pic":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_pic")
        await query.answer()
        await query.message.reply("💸 <b>Send a photo for Payment QR / Banner:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _ppic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if ans.photo:
                pic_id = ans.photo.file_id
                save_fn(premium_plan_photo=pic_id)
                clear_user_session(user_id)
                await client.send_message(user_id, "✅ <b>Payment QR / Photo saved!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_premium_plan")]]))
            else:
                await client.send_message(user_id, "❌ <b>Please send a valid photo!</b>")
                clear_user_session(user_id)
        asyncio.create_task(_ppic_worker())
        return
