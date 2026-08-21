# ⏰ TOKEN VERIFICATION SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from clone_plugins.users_api import parse_time_string, format_time_minutes

def master_token_verification_main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ FIRST VERIFICATION", callback_data="master_token_verification:1")],
        [InlineKeyboardButton("2️⃣ SECOND VERIFICATION", callback_data="master_token_verification:2")],
        [InlineKeyboardButton("3️⃣ THIRD VERIFICATION", callback_data="master_token_verification:3")],
        [InlineKeyboardButton("📢 VERIFY LOG CHANNEL", callback_data="master_verify_log_channel")],
        [InlineKeyboardButton("🪧 BACK", callback_data="settings")]
    ])

def master_single_token_verification_markup(slot: int, is_on: bool):
    prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
    status_icon = "✅" if is_on else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔗 {prefix} VERIFY SHORTNER", callback_data=f"m_v_shortner:{slot}")],
        [InlineKeyboardButton(f"🍿 {prefix} VERIFY TUTORIAL", callback_data=f"m_v_tutorial:{slot}")],
        [InlineKeyboardButton(f"⏰ {prefix} VERIFY TIME", callback_data=f"m_v_time:{slot}")],
        [InlineKeyboardButton("👥 TOTAL USER VERIFIED TODAY", callback_data=f"m_v_stats:{slot}")],
        [InlineKeyboardButton(f"🔒 {prefix} VERIFY - {status_icon}", callback_data=f"m_v_toggle:{slot}")],
        [InlineKeyboardButton("🪧 BACK", callback_data="master_token_main")]
    ])

async def handle_token_callbacks(client, query, data, user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn):
    me = client.me
    if data in ("master_token_main", "master_token_verification", "cset_token_main", "cset_token_verification"):
        text = (
            "⏰ <b>TOKEN VERIFICATION:</b>\n\n"
            "<b>TOKEN VERIFICATION: A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=master_token_verification_main_markup())

    if data.startswith("master_token_verification:") or data.startswith("cset_token_verification:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False))
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        return await edit_or_reply_fn(query, text, reply_markup=master_single_token_verification_markup(slot, is_on))

    if data.startswith("m_v_toggle:") or data.startswith("cset_v_toggle:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        new_state = not bool(v_cfg.get("is_on", False))
        v_cfg["is_on"] = new_state
        save_fn(**{v_key: v_cfg})
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        await query.answer(f"Verification {'Enabled' if new_state else 'Disabled'}!")
        return await edit_or_reply_fn(query, text, reply_markup=master_single_token_verification_markup(slot, new_state))

    if data.startswith("m_v_stats:") or data.startswith("cset_v_stats:"):
        slot = int(data.split(":")[1])
        today_count = r.get(f"verified_today_{slot}", 0)
        bot_title = me.first_name or me.username or "ASH BOT"
        return await query.answer(f"{bot_title}\n\nTotal Verified Today - {today_count}", show_alert=True)

    if data.startswith("m_v_shortner:") or data.startswith("cset_v_shortner:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        site = v_cfg.get("shortner_site") or "Not Set"
        api = v_cfg.get("shortner_api") or "Not Set"
        text = (
            f"🔗 <b>{prefix} VERIFY SHORTNER:</b>\n\n"
            f"🌐 <b>WEBSITE / DOMAIN:</b> <code>{site}</code>\n"
            f"🔑 <b>API KEY:</b> <code>{api}</code>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET SHORTNER", callback_data=f"m_set_v_shortner:{slot}")],
            [InlineKeyboardButton("DELETE SHORTNER", callback_data=f"m_del_v_shortner:{slot}")],
            [InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_shortner:") or data.startswith("cset_v_del_short:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg.pop("shortner_site", None)
        v_cfg.pop("shortner_api", None)
        save_fn(**{v_key: v_cfg})
        await query.answer("Shortener deleted!")
        return await handle_token_callbacks(client, query, f"m_v_shortner:{slot}", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data.startswith("m_set_v_shortner:") or data.startswith("cset_v_set_short:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"m_v_shortner_{slot}")
        await query.answer()
        
        await query.message.reply(
            f"🔗 <b>{prefix} SHORTNER WEBSITE:</b>\n\n"
            "<b>Send your shortener website URL (e.g. <code>shareus.io</code> or <code>https://modijiurl.com</code>):</b>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        
        async def _shortner_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            site = (ans.text or "").strip()
            if site == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            site = site.replace("http://", "").replace("https://", "").strip("/")
            
            await client.send_message(
                user_id,
                f"🔑 <b>{prefix} SHORTNER API KEY:</b>\n\n"
                f"<b>Send your API key for <code>{site}</code>:</b>\n\n"
                "<i>Send /cancel to abort.</i>"
            )
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            api_key = (ans2.text or "").strip()
            if api_key == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            
            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["shortner_site"] = site
            v_cfg["shortner_api"] = api_key
            save_fn(**{v_key: v_cfg})
            clear_user_session(user_id)
            
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} SHORTNER CONFIGURED SUCCESSFULLY!</b>\n\n"
                f"🌐 <b>Site:</b> <code>{site}</code>\n"
                f"🔑 <b>API:</b> <code>{api_key}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_shortner_worker())
        return

    if data.startswith("m_v_tutorial:") or data.startswith("cset_v_tutorial:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        tut = v_cfg.get("tutorial") or "Not Set"
        text = (
            f"🍿 <b>{prefix} VERIFY TUTORIAL:</b>\n\n"
            f"📹 <b>VIDEO / LINK:</b> <code>{tut}</code>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TUTORIAL", callback_data=f"m_set_v_tut:{slot}")],
            [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"m_del_v_tut:{slot}")],
            [InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_tut:") or data.startswith("cset_v_del_tut:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg.pop("tutorial", None)
        save_fn(**{v_key: v_cfg})
        await query.answer("Tutorial deleted!")
        return await handle_token_callbacks(client, query, f"m_v_tutorial:{slot}", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data.startswith("m_set_v_tut:") or data.startswith("cset_v_set_tut:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"m_v_tut_{slot}")
        await query.answer()
        await query.message.reply(
            f"🍿 <b>{prefix} VERIFY TUTORIAL:</b>\n\n"
            "<b>Send your tutorial video link (must start with http:// or https://):</b>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        async def _tut_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t_url = (ans.text or "").strip()
            if t_url == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            if not (t_url.startswith("http://") or t_url.startswith("https://")):
                await client.send_message(user_id, "❌ <b>Invalid URL. Must start with http:// or https://.</b>")
                clear_user_session(user_id)
                return
            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["tutorial"] = t_url
            save_fn(**{v_key: v_cfg})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} TUTORIAL SAVED!</b>\n\n<code>{t_url}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_tut_worker())
        return

    if data.startswith("m_v_time:") or data.startswith("cset_v_time:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        mins = v_cfg.get("time", 1440)
        time_str = format_time_minutes(mins)
        text = (
            f"⏰ <b>{prefix} VERIFY TIME:</b>\n\n"
            f"⏳ <b>CURRENT DURATION:</b> <code>{time_str}</code> ({mins} Minutes)"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET VERIFY TIME", callback_data=f"m_set_v_time:{slot}")],
            [InlineKeyboardButton("RESET TIME", callback_data=f"m_del_v_time:{slot}")],
            [InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_time:") or data.startswith("cset_v_del_time:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["time"] = 1440
        save_fn(**{v_key: v_cfg})
        await query.answer("Time reset to 24 Hours!")
        return await handle_token_callbacks(client, query, f"m_v_time:{slot}", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data.startswith("m_set_v_time:") or data.startswith("cset_v_set_time:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"m_v_time_{slot}")
        await query.answer()
        await query.message.reply(
            f"⏰ <b>{prefix} VERIFY TIME:</b>\n\n"
            "<b>Send verification duration (e.g. <code>12 hours</code>, <code>1 day</code>, <code>30 mins</code>):</b>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        async def _time_worker():
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
            mins = parse_time_string(t_txt)
            if not mins or mins <= 0:
                await client.send_message(user_id, "❌ <b>Invalid time format. Example: 12 hours, 1 day, 45 mins.</b>")
                clear_user_session(user_id)
                return
            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["time"] = mins
            save_fn(**{v_key: v_cfg})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} VERIFY TIME UPDATED!</b>\n\n⏳ <b>New Duration:</b> <code>{format_time_minutes(mins)}</code> ({mins} mins)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_time_worker())
        return

    # Verify Log Channel
    if data in ("master_verify_log_channel", "cset_verify_log_channel"):
        log_ch = r.get("verify_log_channel") or "Not Set"
        text = (
            "📢 <b>VERIFY LOG CHANNEL:</b>\n\n"
            f"🆔 <b>CURRENT LOG CHANNEL:</b> <code>{log_ch}</code>\n\n"
            "<b>All verification activities and token logs will be forwarded to this channel.</b>"
        )
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET LOG CHANNEL", callback_data="m_set_v_log")],
            [InlineKeyboardButton("DELETE LOG CHANNEL", callback_data="m_del_v_log")],
            [InlineKeyboardButton("🪧 BACK", callback_data="master_token_main")]
        ]))

    if data in ("m_del_v_log", "cset_del_v_log"):
        save_fn(verify_log_channel=None)
        await query.answer("Verify log channel deleted!")
        return await handle_token_callbacks(client, query, "master_verify_log_channel", user_id, r, save_fn, get_rec_fn, cancel_listeners_fn, edit_or_reply_fn)

    if data in ("m_set_v_log", "cset_set_v_log"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_v_log")
        await query.answer()
        await query.message.reply(
            "📢 <b>SET VERIFY LOG CHANNEL:</b>\n\n"
            "<b>Forward a message from your channel or send the Channel ID (e.g. <code>-1001234567890</code>):</b>\n\n"
            "<i>Make sure this bot is an ADMIN in the channel! Send /cancel to abort.</i>"
        )
        async def _log_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if (ans.text or "").strip() == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            ch_id = None
            if ans.forward_from_chat:
                ch_id = ans.forward_from_chat.id
            elif ans.text and ans.text.strip().lstrip("-").isdigit():
                ch_id = int(ans.text.strip())
            if not ch_id:
                await client.send_message(user_id, "❌ <b>Invalid channel. Please forward a message from the channel.</b>")
                clear_user_session(user_id)
                return
            try:
                t_msg = await client.send_message(ch_id, "✅ <b>Verify log channel connected successfully!</b>")
                await t_msg.delete()
            except Exception as e:
                await client.send_message(user_id, f"❌ <b>Bot is not admin in channel! Error:</b> {e}")
                clear_user_session(user_id)
                return
            save_fn(verify_log_channel=ch_id)
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>VERIFY LOG CHANNEL CONNECTED!</b>\n\n🆔 <b>Channel ID:</b> <code>{ch_id}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="master_token_main")]])
            )
        asyncio.create_task(_log_worker())
        return
