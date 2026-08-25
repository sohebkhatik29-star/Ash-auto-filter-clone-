# 🎯 TOKEN VERIFICATION SETTINGS MODULE
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from clone_plugins.users_api import parse_time_string, format_time_minutes


def slot_name(slot: int) -> str:
    return "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")


def token_verification_main_markup(r=None, prefix_cb="cset", target_bid=None):
    r = r or {}
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    if target_bid:
        back_cb = f"manage_clone:{target_bid}"
    else:
        back_cb = "settings" if prefix_cb == "master" else "cset_monetization"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 FIRST VERIFICATION", callback_data=f"{cb}_token_verification:1{bid_suffix}")],
        [InlineKeyboardButton("🎯 SECOND VERIFICATION", callback_data=f"{cb}_token_verification:2{bid_suffix}")],
        [InlineKeyboardButton("🎯 THIRD VERIFICATION", callback_data=f"{cb}_token_verification:3{bid_suffix}")],
        [InlineKeyboardButton("👥 VERIFY LOG CHANNEL", callback_data=f"{cb}_verify_log_channel{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def single_token_verification_markup(slot: int, is_on: bool, prefix_cb="cset", target_bid=None):
    prefix = slot_name(slot)
    status_icon = "✅" if is_on else "❌"
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_main{bid_suffix}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎟️ {prefix} VERIFY SHORTNER", callback_data=f"{cb}_v_shortner:{slot}{bid_suffix}")],
        [InlineKeyboardButton(f"🍿 {prefix} VERIFY TUTORIAL", callback_data=f"{cb}_v_tutorial:{slot}{bid_suffix}")],
        [InlineKeyboardButton(f"⌛ {prefix} VERIFY TIME", callback_data=f"{cb}_v_time:{slot}{bid_suffix}")],
        [InlineKeyboardButton("👤 TOTAL USER VERIFIED TODAY", callback_data=f"{cb}_v_stats:{slot}{bid_suffix}")],
        [InlineKeyboardButton(f"{prefix} VERIFY - {status_icon}", callback_data=f"{cb}_v_toggle:{slot}{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def shortner_markup(slot: int, prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_verification:{slot}{bid_suffix}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET SHORTLINK", callback_data=f"{cb}_set_v_shortner:{slot}{bid_suffix}")],
        [InlineKeyboardButton("DELETE SHORTLINK", callback_data=f"{cb}_del_v_shortner:{slot}{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def tutorial_markup(slot: int, prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_verification:{slot}{bid_suffix}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET TUTORIAL", callback_data=f"{cb}_set_v_tut:{slot}{bid_suffix}")],
        [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"{cb}_del_v_tut:{slot}{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def verify_time_markup(slot: int, prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_verification:{slot}{bid_suffix}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET VERIFY TIME", callback_data=f"{cb}_set_v_time:{slot}{bid_suffix}")],
        [InlineKeyboardButton("RESET TIME", callback_data=f"{cb}_del_v_time:{slot}{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def log_channel_markup(prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_main{bid_suffix}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET LOG CHANNEL", callback_data=f"{cb}_set_v_log{bid_suffix}")],
        [InlineKeyboardButton("DELETE LOG CHANNEL", callback_data=f"{cb}_del_v_log{bid_suffix}")],
        [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
    ])


def back_to_slot_markup(slot: int, prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_verification:{slot}{bid_suffix}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])


def back_to_main_markup(prefix_cb="cset", target_bid=None):
    cb = "master" if prefix_cb == "master" else "cset"
    bid_suffix = f":{target_bid}" if target_bid else ""
    back_cb = f"{cb}_token_main{bid_suffix}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])


async def handle_token_callbacks(client, query, data, user_id, r, save_fn, get_rec_fn=None, cancel_listeners_fn=None, edit_or_reply_fn=None, target_bid=None):
    try:
        await query.answer()
    except Exception:
        pass

    if not target_bid and ":" in str(data):
        parts = str(data).split(":")
        for p in parts:
            if p.isdigit() and len(p) >= 6:
                target_bid = int(p)
                break

    me = getattr(client, "me", None)
    prefix_cb = "master" if str(data).startswith("master_") or str(data).startswith("m_") or target_bid else "cset"

    async def clean_show(txt, reply_markup=None):
        msg = getattr(query, "message", None) or query
        if msg and (getattr(msg, "photo", None) or getattr(msg, "media", None)):
            try:
                await msg.delete()
            except Exception:
                pass
            return await client.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)
        if edit_or_reply_fn:
            return await edit_or_reply_fn(query, txt, reply_markup=reply_markup)
        try:
            return await query.edit_message_text(txt, reply_markup=reply_markup)
        except Exception:
            return await query.message.reply(txt, reply_markup=reply_markup)

    # 1. Main Token Verification Screen
    if data in ("master_token_main", "cset_token_main", "master_token_verification", "cset_token_verification") or str(data).startswith(("master_token_main:", "cset_token_main:")):
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        text = (
            "🎯 <b>TOKEN VERIFICATION:</b>\n\n"
            "<blockquote>TOKEN VERIFICATION: A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</blockquote>"
        )
        return await clean_show(text, reply_markup=token_verification_main_markup(curr_r, prefix_cb, target_bid=target_bid))

    # 2. Slot Screen (1, 2, 3)
    if str(data).startswith(("master_token_verification:", "cset_token_verification:")):
        slot = int(data.split(":")[1])
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = curr_r.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False)) or bool(curr_r.get(f"is_verify_{slot}", False))
        prefix = slot_name(slot)
        text = f"🎯 <b>{prefix} TOKEN VERIFICATION:</b>"
        return await clean_show(text, reply_markup=single_token_verification_markup(slot, is_on, prefix_cb, target_bid=target_bid))

    # 3. Toggle Slot (ON/OFF)
    if str(data).startswith(("master_v_toggle:", "m_v_toggle:", "cset_v_toggle:")):
        slot = int(data.split(":")[1])
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = dict(curr_r.get(v_key, {}))
        curr_state = bool(v_cfg.get("is_on", False)) or bool(curr_r.get(f"is_verify_{slot}", False))
        new_state = not curr_state
        v_cfg["is_on"] = new_state
        curr_r[v_key] = v_cfg
        save_fn(**{v_key: v_cfg, f"is_verify_{slot}": new_state})
        prefix = slot_name(slot)
        text = f"🎯 <b>{prefix} TOKEN VERIFICATION:</b>"
        await query.answer(f"Verification {'Enabled' if new_state else 'Disabled'}!")
        return await clean_show(text, reply_markup=single_token_verification_markup(slot, new_state, prefix_cb, target_bid=target_bid))

    # 4. Stats Alert
    if str(data).startswith(("master_v_stats:", "m_v_stats:", "cset_v_stats:")):
        slot = int(data.split(":")[1])
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        today_count = curr_r.get(f"verified_today_{slot}", 0)
        bot_title = getattr(me, "first_name", None) or getattr(me, "username", None) or "ASH BOT"
        return await query.answer(f"{bot_title}\n\nTotal Verified Today - {today_count}", show_alert=True)

    # 5. Verify Shortner Screen
    if str(data).startswith(("master_v_shortner:", "m_v_shortner:", "cset_v_shortner:")):
        slot = int(data.split(":")[1])
        prefix = slot_name(slot)
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = curr_r.get(v_key, {})
        site = v_cfg.get("shortner_site") or v_cfg.get("site") or "Not Set"
        api = v_cfg.get("shortner_api") or v_cfg.get("api") or "Not Set"
        text = (
            f"🎟️ <b>{prefix} VERIFY SHORTNER:</b>\n\n"
            "<blockquote>LINK SHORTENER: A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</blockquote>\n\n"
            f"<b>URL -</b> <code>{site}</code>\n"
            f"<b>API -</b> <code>{api}</code>"
        )
        return await clean_show(text, reply_markup=shortner_markup(slot, prefix_cb, target_bid=target_bid))

    # 6. Delete Shortner
    if str(data).startswith(("master_del_v_shortner:", "m_del_v_shortner:", "cset_del_v_shortner:", "cset_v_del_short:", "master_v_del_short:")):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_cfg = dict(curr_r.get(v_key, {}))
        v_cfg.pop("shortner_site", None)
        v_cfg.pop("site", None)
        v_cfg.pop("shortner_api", None)
        v_cfg.pop("api", None)
        curr_r[v_key] = v_cfg
        save_fn(**{v_key: v_cfg})
        await query.answer("Shortlink Deleted!")
        text = "<b>SUCCESSFULLY DELETED SHORTLINK</b> ✅"
        return await clean_show(text, reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid))

    # 7. Set Shortner Flow
    if str(data).startswith(("master_set_v_shortner:", "m_set_v_shortner:", "cset_set_v_shortner:", "cset_v_set_short:", "master_v_set_short:")):
        slot = int(data.split(":")[1])
        if cancel_listeners_fn:
            cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"set_v_shortner_{slot}")
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A SHORTLINK URL...</b>\n\n"
                "<b>FORMAT :</b>\n\n"
                "https://vjlink.online - ❌\n\n"
                "vjlink.online - ✅\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
        )

        async def _shortner_worker():
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
            site = (ans.text or "").strip()
            if site == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    user_id,
                    "❌ <b>Cancelled.</b>",
                    reply_markup=back_to_slot_markup(slot, prefix_cb)
                )
                return

            site = site.replace("http://", "").replace("https://", "").strip().rstrip("/")
            if not site:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Invalid site.</b>")
                clear_user_session(user_id)
                return

            try:
                await prompt_msg.delete()
            except Exception:
                pass

            prompt2 = await client.send_message(
                user_id,
                "<b>SEND ME SHORTLINK API...</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt2.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            api_key = (ans2.text or "").strip()
            if api_key == "/cancel":
                try:
                    await prompt2.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    user_id,
                    "❌ <b>Cancelled.</b>",
                    reply_markup=back_to_slot_markup(slot, prefix_cb)
                )
                return

            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn() if callable(get_rec_fn) else r
            v_cfg = dict(curr_r.get(v_key, {}))
            v_cfg["shortner_site"] = site
            v_cfg["site"] = site
            v_cfg["shortner_api"] = api_key
            v_cfg["api"] = api_key
            v_cfg["is_on"] = True
            curr_r[v_key] = v_cfg
            save_fn(**{v_key: v_cfg, f"is_verify_{slot}": True})
            clear_user_session(user_id)

            try:
                await prompt2.delete()
            except Exception:
                pass

            await client.send_message(
                user_id,
                "<b>SUCCESSFULLY SET SHORTLINK</b> ✅",
                reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid)
            )
        asyncio.create_task(_shortner_worker())
        return

    # 8. Verify Tutorial Screen
    if str(data).startswith(("master_v_tutorial:", "m_v_tutorial:", "cset_v_tutorial:")):
        slot = int(data.split(":")[1])
        prefix = slot_name(slot)
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = curr_r.get(v_key, {})
        tut = v_cfg.get("tutorial") or "Not Set"
        text = (
            f"🍿 <b>{prefix} VERIFY TUTORIAL:</b>\n\n"
            "<blockquote>TUTORIAL LINK: THE PROCESS VIDEO OF OPENING LINK OF SHORTER. LINK OF VIDEO OR CHANNEL WHERE VIDEO IS UPLOADED. VIDEO MEANS VIDEO OF HOW TO OPEN LINK.</blockquote>\n\n"
            f"<b>LINK -</b> <code>{tut}</code>"
        )
        return await clean_show(text, reply_markup=tutorial_markup(slot, prefix_cb, target_bid=target_bid))

    # 9. Delete Tutorial
    if str(data).startswith(("master_del_v_tut:", "m_del_v_tut:", "cset_del_v_tut:", "cset_v_del_tut:", "master_v_del_tut:")):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_cfg = dict(curr_r.get(v_key, {}))
        v_cfg.pop("tutorial", None)
        curr_r[v_key] = v_cfg
        save_fn(**{v_key: v_cfg})
        await query.answer("Tutorial Deleted!")
        text = "<b>SUCCESSFULLY DELETED TUTORIAL LINK</b> ✅"
        return await clean_show(text, reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid))

    # 10. Set Tutorial Flow
    if str(data).startswith(("master_set_v_tut:", "m_set_v_tut:", "cset_set_v_tut:", "cset_v_set_tut:", "master_v_set_tut:")):
        slot = int(data.split(":")[1])
        if cancel_listeners_fn:
            cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"set_v_tut_{slot}")
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A TUTORIAL LINK...</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
        )
        async def _tut_worker():
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
            t_url = (ans.text or "").strip()
            if t_url == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    user_id,
                    "❌ <b>Cancelled.</b>",
                    reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid)
                )
                return
            if not (t_url.startswith("http://") or t_url.startswith("https://") or t_url.startswith("t.me/")):
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Invalid URL. Must start with http://, https:// or t.me/</b>")
                clear_user_session(user_id)
                return
            if t_url.startswith("t.me/"):
                t_url = f"https://{t_url}"
            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn() if callable(get_rec_fn) else r
            v_cfg = dict(curr_r.get(v_key, {}))
            v_cfg["tutorial"] = t_url
            curr_r[v_key] = v_cfg
            save_fn(**{v_key: v_cfg})
            clear_user_session(user_id)

            try:
                await prompt_msg.delete()
            except Exception:
                pass

            await client.send_message(
                user_id,
                "<b>SUCCESSFULLY SET TUTORIAL LINK</b> ✅",
                reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid)
            )
        asyncio.create_task(_tut_worker())
        return

    # 11. Verify Time Screen
    if str(data).startswith(("master_v_time:", "m_v_time:", "cset_v_time:")):
        slot = int(data.split(":")[1])
        prefix = slot_name(slot)
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = curr_r.get(v_key, {})
        mins = int(v_cfg.get("time", v_cfg.get("time_minutes", 1440)))
        time_str = format_time_minutes(mins)
        text = (
            f"⌛ <b>{prefix} VERIFY TIME:</b>\n\n"
            "<blockquote>VERIFICATION TIME: DURATION FOR WHICH USER GETS BOT ACCESS AFTER COMPLETING ACCESS TOKEN.</blockquote>\n\n"
            f"<b>TIME -</b> <code>{time_str}</code> ({mins} Minutes)"
        )
        return await clean_show(text, reply_markup=verify_time_markup(slot, prefix_cb, target_bid=target_bid))

    # 12. Reset Verify Time
    if str(data).startswith(("master_del_v_time:", "m_del_v_time:", "cset_del_v_time:", "cset_v_del_time:", "master_v_del_time:")):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        v_cfg = dict(curr_r.get(v_key, {}))
        v_cfg["time"] = 1440
        v_cfg["time_minutes"] = 1440
        curr_r[v_key] = v_cfg
        save_fn(**{v_key: v_cfg})
        await query.answer("Time reset to 24 Hours!")
        prefix = slot_name(slot)
        text = (
            f"⌛ <b>{prefix} VERIFY TIME:</b>\n\n"
            "<blockquote>VERIFICATION TIME: DURATION FOR WHICH USER GETS BOT ACCESS AFTER COMPLETING ACCESS TOKEN.</blockquote>\n\n"
            f"<b>TIME -</b> <code>24 Hours</code> (1440 Minutes)"
        )
        return await clean_show(text, reply_markup=verify_time_markup(slot, prefix_cb, target_bid=target_bid))

    # 13. Set Verify Time Flow
    if str(data).startswith(("master_set_v_time:", "m_set_v_time:", "cset_set_v_time:", "cset_v_set_time:", "master_v_set_time:")):
        slot = int(data.split(":")[1])
        if cancel_listeners_fn:
            cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"set_v_time_{slot}")
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME VERIFY TIME...</b>\n\n"
                "<b>FORMAT :</b>\n"
                "<code>10 minutes</code>, <code>1 hour</code>, <code>24 hours</code>, <code>7 days</code>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
        )
        async def _time_worker():
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
            t_txt = (ans.text or "").strip()
            if t_txt == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    user_id,
                    "❌ <b>Cancelled.</b>",
                    reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid)
                )
                return
            mins = parse_time_string(t_txt)
            if not mins or mins <= 0:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Invalid time format. Example: 10 minutes, 1 hour, 24 hours.</b>")
                clear_user_session(user_id)
                return
            v_key = f"verify_{slot}" if slot > 1 else "verify_1"
            curr_r = get_rec_fn() if callable(get_rec_fn) else r
            v_cfg = dict(curr_r.get(v_key, {}))
            v_cfg["time"] = mins
            v_cfg["time_minutes"] = mins
            curr_r[v_key] = v_cfg
            save_fn(**{v_key: v_cfg})
            clear_user_session(user_id)

            try:
                await prompt_msg.delete()
            except Exception:
                pass

            await client.send_message(
                user_id,
                "<b>SUCCESSFULLY SET VERIFY TIME</b> ✅",
                reply_markup=back_to_slot_markup(slot, prefix_cb, target_bid=target_bid)
            )
        asyncio.create_task(_time_worker())
        return

    # 14. Verify Log Channel Screen
    if data in ("master_verify_log_channel", "cset_verify_log_channel") or str(data).startswith(("master_verify_log_channel", "cset_verify_log_channel")):
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        log_ch = curr_r.get("verify_log_channel") or "Not Set"
        text = (
            "👥 <b>VERIFY LOG CHANNEL:</b>\n\n"
            "<blockquote>ALL VERIFICATION ACTIVITIES AND TOKEN LOGS WILL BE FORWARDED TO THIS CHANNEL.</blockquote>\n\n"
            f"<b>CHANNEL -</b> <code>{log_ch}</code>"
        )
        return await clean_show(text, reply_markup=log_channel_markup(prefix_cb, target_bid=target_bid))

    # 15. Delete Verify Log Channel
    if data in ("m_del_v_log", "master_del_v_log", "cset_del_v_log", "cset_v_del_log") or str(data).startswith(("m_del_v_log", "master_del_v_log", "cset_del_v_log", "cset_v_del_log")):
        curr_r = get_rec_fn() if callable(get_rec_fn) else r
        curr_r["verify_log_channel"] = None
        save_fn(verify_log_channel=None)
        await query.answer("Verify log channel deleted!")
        text = "<b>SUCCESSFULLY DELETED LOG CHANNEL</b> ✅"
        return await clean_show(text, reply_markup=back_to_main_markup(prefix_cb, target_bid=target_bid))

    # 16. Set Verify Log Channel Flow
    if data in ("m_set_v_log", "master_set_v_log", "cset_set_v_log", "cset_v_set_log") or str(data).startswith(("m_set_v_log", "master_set_v_log", "cset_set_v_log", "cset_v_set_log")):
        if cancel_listeners_fn:
            cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_v_log")
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "👥 <b>SET VERIFY LOG CHANNEL:</b>\n\n"
                "<b>Forward a message from your channel or send the Channel ID (e.g. <code>-1001234567890</code>):</b>\n\n"
                "<i>Make sure this bot is an ADMIN in the channel! Send /cancel to abort.</i>"
            )
        )
        async def _log_worker():
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
            if (ans.text or "").strip() == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                await client.send_message(
                    user_id,
                    "❌ <b>Cancelled.</b>",
                    reply_markup=back_to_main_markup(prefix_cb, target_bid=target_bid)
                )
                return
            ch_id = None
            if ans.forward_from_chat:
                ch_id = ans.forward_from_chat.id
            elif ans.text and ans.text.strip().lstrip("-").isdigit():
                ch_id = int(ans.text.strip())
            if not ch_id:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, "❌ <b>Invalid channel. Please forward a message from the channel.</b>")
                clear_user_session(user_id)
                return
            try:
                t_msg = await client.send_message(ch_id, "✅ <b>Verify log channel connected successfully!</b>")
                await t_msg.delete()
            except Exception as e:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                await client.send_message(user_id, f"❌ <b>Bot is not admin in channel! Error:</b> {e}")
                clear_user_session(user_id)
                return
            curr_r = get_rec_fn() if callable(get_rec_fn) else r
            curr_r["verify_log_channel"] = ch_id
            save_fn(verify_log_channel=ch_id)
            clear_user_session(user_id)

            try:
                await prompt_msg.delete()
            except Exception:
                pass

            await client.send_message(
                user_id,
                "<b>SUCCESSFULLY SET LOG CHANNEL</b> ✅",
                reply_markup=back_to_main_markup(prefix_cb, target_bid=target_bid)
            )
        asyncio.create_task(_log_worker())
        return
