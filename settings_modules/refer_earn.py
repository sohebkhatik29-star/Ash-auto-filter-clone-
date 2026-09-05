# 🌍 REFER AND EARN SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def handle_refer_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data in ("master_refer_earn", "cset_refer_earn"):
        ref_on = bool(r.get("refer_enabled", False))
        pts = r.get("refer_points", 10)
        target = r.get("refer_target", 50)
        status_txt = "ON ✅" if ref_on else "OFF ❌"
        text = (
            "🌍 <b>REFER AND EARN:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n"
            f"• <b>POINTS PER REFERRAL:</b> <code>{pts}</code>\n"
            f"• <b>POINTS TO UNLOCK REWARD:</b> <code>{target}</code>\n\n"
            f"🔗 <b>YOUR REFERRAL LINK:</b>\n<code>https://t.me/{me.username}?start=ref_{user_id}</code>\n\n"
            "<b>Reward users for inviting their friends to the bot!</b>"
        )
        tgl_btn = "DISABLE REFER & EARN" if ref_on else "ENABLE REFER & EARN"
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_refer")],
            [InlineKeyboardButton("SET POINTS PER REFER", callback_data="m_set_refer_pts")],
            [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
        ]))

    if data == "m_tgl_refer":
        new_s = not bool(r.get("refer_enabled", False))
        save_fn(refer_enabled=new_s)
        await query.answer(f"Refer & Earn {'Enabled' if new_s else 'Disabled'}!")
        return await handle_refer_callbacks(client, query, "master_refer_earn", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data == "m_set_refer_pts":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_refer_pts")
        try:
            await query.answer()
        except Exception:
            pass
        try:
            if getattr(query, "message", None):
                await query.message.delete()
        except Exception:
            pass
        prompt_msg = await client.send_message(
            chat_id=user_id,
            text="🌍 <b>Send points to award per referral (e.g. <code>10</code>):</b>\n\n<i>Send /cancel to abort.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_refer_earn")]])
        )
        async def _ref_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            try:
                if ans:
                    await ans.delete()
            except Exception:
                pass
            t = (ans.text or "").strip()
            if t == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_refer_earn")]]))
                clear_user_session(user_id)
                return
            if not t.isdigit():
                await client.send_message(user_id, "❌ <b>Must be a number.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_refer_earn")]]))
                clear_user_session(user_id)
                return
            save_fn(refer_points=int(t))
            clear_user_session(user_id)
            await client.send_message(user_id, f"✅ <b>Points set to:</b> {t}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_refer_earn")]]))
        asyncio.create_task(_ref_worker())
        return
