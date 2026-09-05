# 📢 FORCE SUBSCRIBE SETTINGS MODULE
import asyncio
import time
from pyrogram import enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from plugins.clone import mongo_db
from config import BOT_USERNAME

# ----------------- TRACKED PROMPTS & CLEANUP ----------------- #
_FSUB_TRACKED_MSGS = {}

def track_fsub_msg(user_id, msg_id):
    if not user_id or not msg_id:
        return
    uid = int(user_id)
    if uid not in _FSUB_TRACKED_MSGS:
        _FSUB_TRACKED_MSGS[uid] = set()
    _FSUB_TRACKED_MSGS[uid].add(int(msg_id))

async def cleanup_fsub_msgs(client, user_id, except_ids=None):
    if not user_id:
        return
    uid = int(user_id)
    msg_ids = list(_FSUB_TRACKED_MSGS.get(uid, set()))
    _FSUB_TRACKED_MSGS[uid] = set()
    exc = {int(x) for x in except_ids} if except_ids else set()
    for mid in msg_ids:
        if mid not in exc:
            try:
                await client.delete_messages(chat_id=uid, message_ids=mid)
            except Exception:
                pass

# ----------------- MAIN FSUB UI TEXT & MENUS ----------------- #

FSUB_MAIN_DESC = (
    "『 <b>FORCE SUBSCRIBE:</b>\n"
    "--------------------------------------------------\n"
    "<b>FORCE SUBSCRIBE:</b>\n"
    "A TELEGRAM BOT FEATURE FORCING USERS TO SUBSCRIBE TO SPECIFIC CHANNELS BEFORE ACCESSING CONTENT.\n\n"
    "<b>NORMAL FSUB:</b>\n"
    "REQUIRES THE USER TO CLICK A JOIN BUTTON ON A CHANNEL OR GROUP, THEN BOT CHECKS MEMBERSHIP INSTANTLY TO UNLOCK RESTRICTED CONTENT OR CHAT ACCESS.\n\n"
    "<b>JOIN REQUEST FSUB:</b>\n"
    "REQUIRES THE USER TO SEND A REQUEST TO JOIN A PRIVATE CHANNEL OR GROUP THEN USER CAN ACCESS CONTENT.\n\n"
    "<b>YOU CAN ADD MULTIPLE CHANNELS</b>\n"
    "-------------------------------------------------- 』\n"
)

FSUB_MSG_DESC = (
    "『 📝 <b>FORCE SUBSCRIBE MESSAGE:</b>\n"
    "--------------------------------------------------\n"
    "<b>FORCE SUBSCRIBE MESSAGE:</b> YOU CAN CUSTOMISE YOUR CLONE BOT FORCE SUBSCRIBE MESSAGE ANY WAY YOU LIKE.\n"
    "-------------------------------------------------- 』"
)

FSUB_BUTTON_DESC = (
    "⚪ <b>FORCE SUBSCRIBE MESSAGE BUTTON:</b>\n"
    "--------------------------------------------------\n"
    "<b>CREATE CUSTOM URL BUTTONS FOR YOUR MESSAGE.</b>\n\n"
    "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
    "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
    "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
    "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>\n"
    "--------------------------------------------------"
)

DEFAULT_FSUB_TEXT = "👉 <b>PLEASE JOIN MY UPDATES CHANNEL AND THEN CLICK ON TRY AGAIN BUTTON</b> 👇"


# ----------------- FAKE BUTTON BUILDER ----------------- #

async def run_fsub_button_builder(client, user_id, save_fn, cancel_listeners_fn, prev_msg=None):
    if prev_msg:
        try:
            await prev_msg.delete()
        except Exception:
            pass
    await cleanup_fsub_msgs(client, user_id)
    cancel_listeners_fn(client, user_id, user_id)
    sess_token = start_user_session(user_id, "fsub_btn_builder")
    rows = []
    row_idx = 1

    while is_user_session_active(user_id, sess_token):
        count_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("1️⃣ One Button"), KeyboardButton("2️⃣ Two Buttons")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        msg_text = (
            f"🪧 <b>ROW {row_idx} ❞</b>\n\n"
            "<i>How many buttons do you want in this row?</i>\n\n"
            "<i>Please choose an option using the keyboard below.</i>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        prompt_cnt = await client.send_message(chat_id=user_id, text=msg_text, reply_markup=count_kb)
        track_fsub_msg(user_id, prompt_cnt.id)

        btn_count = 0
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt_cnt.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return

            try:
                await prompt_cnt.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            txt = (ans.text or "").strip()
            if txt == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return
            if "1" in txt or "One" in txt:
                btn_count = 1
                break
            elif "2" in txt or "Two" in txt:
                btn_count = 2
                break
            else:
                invalid_msg = "❌ <b>INVALID CHOICE</b>\n\n<i>Please select 1 or 2 using the keyboard.</i>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
                prompt_cnt = await client.send_message(chat_id=user_id, text=invalid_msg, reply_markup=count_kb)
                track_fsub_msg(user_id, prompt_cnt.id)

        if not is_user_session_active(user_id, sess_token):
            return

        row_buttons = []
        for b_i in range(1, btn_count + 1):
            btn_num = b_i if btn_count > 1 else 1

            # Step A: Button Text
            p_txt_msg = await client.send_message(
                chat_id=user_id,
                text=f"🔤 <b>BUTTON {btn_num} ❞</b>\n\n<i>Send the button text.</i>\n\n<i>Maximum length: 64 characters</i>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>",
                reply_markup=ReplyKeyboardRemove()
            )
            track_fsub_msg(user_id, p_txt_msg.id)

            b_text = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    try:
                        await p_txt_msg.delete()
                    except Exception:
                        pass
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Timeout. Process cancelled.</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    clear_user_session(user_id)
                    return

                try:
                    await p_txt_msg.delete()
                except Exception:
                    pass
                try:
                    await ans.delete()
                except Exception:
                    pass

                t = (ans.text or "").strip()
                if t == "/cancel":
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Process Cancelled Successfully!</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    clear_user_session(user_id)
                    return
                if not t or len(t) > 64:
                    p_txt_msg = await client.send_message(chat_id=user_id, text="⚠️ <i>Text must be 1 to 64 characters. Send again:</i>")
                    track_fsub_msg(user_id, p_txt_msg.id)
                    continue
                b_text = t
                break

            if not is_user_session_active(user_id, sess_token):
                return

            # Step B: Button URL
            p_url_msg = await client.send_message(
                chat_id=user_id,
                text=f"🔗 <b>BUTTON {btn_num} URL ❞</b>\n\n<i>Send the link for this button.</i>\n\n<i>Must start with http://, https:// or tg://</i>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
            )
            track_fsub_msg(user_id, p_url_msg.id)

            b_url = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    try:
                        await p_url_msg.delete()
                    except Exception:
                        pass
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Timeout. Process cancelled.</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    clear_user_session(user_id)
                    return

                try:
                    await p_url_msg.delete()
                except Exception:
                    pass
                try:
                    await ans.delete()
                except Exception:
                    pass

                u = (ans.text or "").strip()
                if u == "/cancel":
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Process Cancelled Successfully!</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    clear_user_session(user_id)
                    return
                if not (u.startswith("http://") or u.startswith("https://") or u.startswith("tg://")):
                    p_url_msg = await client.send_message(chat_id=user_id, text="⚠️ <i>Invalid URL! Must start with http://, https:// or tg://. Send again:</i>")
                    track_fsub_msg(user_id, p_url_msg.id)
                    continue
                b_url = u
                break

            if not is_user_session_active(user_id, sess_token):
                return

            row_buttons.append({"text": b_text, "url": b_url})

        # Step C: Button Style for this row
        style_kb = ReplyKeyboardMarkup(
            [
                [KeyboardButton("🔵 Primary"), KeyboardButton("⚪ Default")],
                [KeyboardButton("🟢 Success"), KeyboardButton("🔴 Danger")]
            ],
            resize_keyboard=True, one_time_keyboard=True
        )
        p_style_msg = await client.send_message(
            chat_id=user_id,
            text=f"🪧 <b>ROW {row_idx} ❞</b>\n\n<i>Select a button style.</i>\n\n<i>Choose one of the options below.</i>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>",
            reply_markup=style_kb
        )
        track_fsub_msg(user_id, p_style_msg.id)

        b_style = "primary"
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await p_style_msg.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return

            try:
                await p_style_msg.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            st = (ans.text or "").strip().lower()
            if st == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return
            if "danger" in st or "red" in st or "🔴" in st:
                b_style = "danger"
            elif "success" in st or "green" in st or "🟢" in st:
                b_style = "success"
            elif "default" in st or "white" in st or "⚪" in st:
                b_style = "default"
            else:
                b_style = "primary"
            break

        if not is_user_session_active(user_id, sess_token):
            return

        rows.append({"buttons": row_buttons, "style": b_style})

        # Step D: Add Another Row?
        add_more_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Yes"), KeyboardButton("❌ No")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        p_more_msg = await client.send_message(
            chat_id=user_id,
            text="➕ <b>ADD NEW ROW ❞</b>\n\n<i>Do you want to add another row?</i>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>",
            reply_markup=add_more_kb
        )
        track_fsub_msg(user_id, p_more_msg.id)

        add_more = False
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await p_more_msg.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return

            try:
                await p_more_msg.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            ans_txt = (ans.text or "").strip()
            if ans_txt == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                try:
                    temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                    await temp.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                return
            if "yes" in ans_txt.lower() or "✅" in ans_txt:
                add_more = True
                row_idx += 1
                break
            elif "no" in ans_txt.lower() or "❌" in ans_txt:
                add_more = False
                break
            else:
                p_more_msg = await client.send_message(chat_id=user_id, text="⚠️ <i>Please choose Yes or No.</i>", reply_markup=add_more_kb)
                track_fsub_msg(user_id, p_more_msg.id)

        if not is_user_session_active(user_id, sess_token):
            return

        if not add_more:
            break

    clear_user_session(user_id)
    save_fn(fsub_buttons=rows)
    try:
        temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
        await temp.delete()
    except Exception:
        pass
    m = await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]]),
    )
    track_fsub_msg(user_id, m.id)


# ----------------- MAIN CALLBACK HANDLER ----------------- #

async def handle_fsub_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, *args, **kwargs):
    try:
        await query.answer()
    except Exception:
        pass

    target_bid = r.get("bot_id")
    if not target_bid and mongo_db is not None:
        try:
            act = mongo_db.active_clone_edit.find_one({"user_id": int(user_id)})
            if act:
                target_bid = act.get("bot_id")
        except Exception:
            pass

    # 1. Main Force Subscribe Settings Menu
    if data in ("master_fsub_menu", "cset_fsub_menu", "cset_fsub_main") or data.startswith("cset_fsub:"):
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        fsub_on = bool(r.get("fsub_enabled", False))
        raw_channels = r.get("fsub_channels", [])
        if isinstance(raw_channels, list):
            channels = raw_channels
        elif raw_channels:
            channels = [raw_channels]
        else:
            channels = []
        
        bot_type = "clone bot" if target_bid else "bot"
        desc = (
            f"<b>Force Sub</b>\n"
            f"<i>Users can only use your {bot_type} after joining all force sub channels. Clone bots now also support join request mode.</i>\n\n"
            f"<b>You can add up to 6 channels</b>"
        )
        status_line = f"\n\n<b>STATUS:</b> {'ON ✅' if fsub_on else 'OFF ❌'}"
        text = f"{desc}{status_line}"

        buttons = []
        # Channel item buttons
        for idx, ch in enumerate(channels):
            if isinstance(ch, dict):
                title = ch.get("title") or f"Channel {idx+1}"
            else:
                title = str(ch)
            buttons.append([
                InlineKeyboardButton(f"• {title}", callback_data=f"cset_fsub_ch:{idx}"),
                InlineKeyboardButton("✕", callback_data=f"cset_fsub_del_ch:{idx}")
            ])

        if len(channels) < 6:
            buttons.append([InlineKeyboardButton("➕ Add Channel", callback_data="cset_fsub_add")])
        else:
            buttons.append([InlineKeyboardButton("🚫 LIMIT REACHED (6/6)", callback_data="cset_fsub_limit")])

        if fsub_on:
            buttons.append([InlineKeyboardButton("OFF FORCE SUBSCRIBE", callback_data="cset_fsub_toggle")])
        else:
            buttons.append([InlineKeyboardButton("ON FORCE SUBSCRIBE", callback_data="cset_fsub_toggle")])
            
        buttons.append([InlineKeyboardButton("FORCE SUBSCRIBE MESSAGE", callback_data="cset_fsub_msg_menu")])
        is_master = (
            not target_bid
            and (data.startswith("master_") or r.get("type") == "master_config")
        )
        back_cb = "settings" if is_master else "settings_back"
        buttons.append([InlineKeyboardButton("‹ back", callback_data=back_cb)])

        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup(buttons))

    if data == "cset_fsub_limit":
        return await query.answer("❌ You can add maximum 6 channels.", show_alert=True)

    # 2. Toggle FSub Status
    if data in ("m_tgl_fsub", "cset_fsub_toggle"):
        new_status = not bool(r.get("fsub_enabled", False))
        save_fn(fsub_enabled=new_status)
        r["fsub_enabled"] = new_status
        await query.answer(f"Force Subscribe {'Enabled ✅' if new_status else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 3. View / Manage Channel
    if data.startswith("cset_fsub_ch:"):
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        idx = int(data.split(":", 1)[1])
        channels = r.get("fsub_channels", [])
        if idx >= len(channels):
            await query.answer("Channel not found!")
            return await handle_fsub_callbacks(client, query, "cset_fsub_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
        
        ch = channels[idx]
        if isinstance(ch, dict):
            ch_title = ch.get("title", "Unknown")
            ch_id = ch.get("chat_id", "Unknown")
            ch_mode = ch.get("mode", "normal").capitalize()
            ch_link = ch.get("invite_link") or "None"
        else:
            ch_title = str(ch)
            ch_id = str(ch)
            ch_mode = "Normal"
            ch_link = "None"

        info_text = (
            "📢 <b>CHANNEL DETAILS:</b>\n\n"
            f"• <b>TITLE:</b> <b>{ch_title}</b>\n"
            f"• <b>ID:</b> <code>{ch_id}</code>\n"
            f"• <b>MODE:</b> <b>{ch_mode}</b>\n"
            f"• <b>LINK:</b> {ch_link}"
        )
        return await edit_or_reply_fn(query, info_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ DELETE CHANNEL", callback_data=f"cset_fsub_del_ch:{idx}")],
            [InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]
        ]))

    # 4. Delete Channel
    if data.startswith("cset_fsub_del_ch:"):
        idx = int(data.split(":", 1)[1])
        channels = list(r.get("fsub_channels", []))
        if idx < len(channels):
            deleted = channels.pop(idx)
            del_title = deleted.get("title") if isinstance(deleted, dict) else str(deleted)
            save_fn(fsub_channels=channels)
            r["fsub_channels"] = channels
            await query.answer(f"✨ Successfully {del_title} Removed From Forcesub Channels", show_alert=True)
        else:
            await query.answer("Channel not found!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 5. Add Channel Flow
    if data in ("m_add_fsub", "cset_fsub_add"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "fsub_add_ch")
        await query.answer()

        await cleanup_fsub_msgs(client, user_id)

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg_text = (
            "<b>( SET CHANNEL )</b>\n\n"
            "<b>FORWARD A MESSAGE FROM YOUR FORCE SUBSCRIBE CHANNEL WITH FORWARD TAG AND MAKE ME ADMIN IN THAT CHANNEL WITH FULL RIGHTS</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        prompt_msg = await client.send_message(chat_id=user_id, text=prompt_msg_text)
        track_fsub_msg(user_id, prompt_msg.id)

        async def _add_fsub_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            try:
                await prompt_msg.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            txt = (ans.text or "").strip()
            if txt == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return

            chat_id = None
            chat_title = None
            chat_username = None

            if ans.forward_from_chat:
                chat_id = ans.forward_from_chat.id
                chat_title = ans.forward_from_chat.title
                chat_username = ans.forward_from_chat.username
            elif txt:
                try:
                    c = await client.get_chat(int(txt) if txt.lstrip("-").isdigit() else txt)
                    chat_id = c.id
                    chat_title = c.title
                    chat_username = c.username
                except Exception:
                    pass

            if not chat_id:
                m = await client.send_message(
                    user_id,
                    "❌ <b>Please forward a message directly from the channel!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return

            # Verify admin permissions with target bot client
            from plugins.clone import get_clone_client
            target_bid = r.get("bot_id")
            if not target_bid and mongo_db is not None:
                act = mongo_db.active_clone_edit.find_one({"user_id": int(user_id)})
                if act:
                    target_bid = act.get("bot_id")
            
            target_client = get_clone_client(target_bid) if target_bid else None

            is_admin = False
            if target_client:
                try:
                    target_me = target_client.me or (await target_client.get_me())
                    member = await target_client.get_chat_member(chat_id, target_me.id)
                    if member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                        is_admin = True
                except Exception:
                    is_admin = False
            elif target_bid:
                try:
                    target_me = client.me or (await client.get_me())
                    member = await client.get_chat_member(chat_id, target_me.id)
                    if member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                        is_admin = True
                except Exception:
                    is_admin = True
            else:
                try:
                    target_me = client.me or (await client.get_me())
                    member = await client.get_chat_member(chat_id, target_me.id)
                    if member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                        is_admin = True
                except Exception:
                    is_admin = False

            if not is_admin:
                if target_bid:
                    err_msg = (
                        "⚠️ <b>Make Sure Your Clone Bot Is Admin In Your Force Sub Channel</b>\n\n"
                        "<i>Please make your clone bot admin in that channel with full rights and try again.</i>"
                    )
                else:
                    err_msg = (
                        "⚠️ <b>Make Sure Your Bot Is Admin In Your Force Sub Channel</b>\n\n"
                        "<i>Please make me admin in that channel with full rights and try again.</i>"
                    )
                clear_user_session(user_id)
                m = await client.send_message(
                    user_id,
                    err_msg,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                return

            # Prompt mode: Normal or Join Request
            mode_kb = ReplyKeyboardMarkup(
                [[KeyboardButton("Normal"), KeyboardButton("Join Request")]],
                resize_keyboard=True, one_time_keyboard=True
            )
            mode_prompt_msg = await client.send_message(
                chat_id=user_id,
                text="<b>SELECT YOUR MODE WHICH YOU WANT FOR THIS BELOW 👇</b>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>",
                reply_markup=mode_kb
            )
            track_fsub_msg(user_id, mode_prompt_msg.id)

            chosen_mode = "normal"
            while is_user_session_active(user_id, sess_token):
                try:
                    m_ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    try:
                        await mode_prompt_msg.delete()
                    except Exception:
                        pass
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Timeout. Process cancelled.</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    try:
                        temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                        await temp.delete()
                    except Exception:
                        pass
                    clear_user_session(user_id)
                    return

                try:
                    await mode_prompt_msg.delete()
                except Exception:
                    pass
                try:
                    await m_ans.delete()
                except Exception:
                    pass

                m_txt = (m_ans.text or "").strip().lower()
                if m_txt == "/cancel":
                    m = await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>Process Cancelled Successfully!</b>",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]])
                    )
                    track_fsub_msg(user_id, m.id)
                    try:
                        temp = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                        await temp.delete()
                    except Exception:
                        pass
                    clear_user_session(user_id)
                    return

                if "request" in m_txt:
                    chosen_mode = "request"
                    break
                elif "normal" in m_txt:
                    chosen_mode = "normal"
                    break
                else:
                    mode_prompt_msg = await client.send_message(chat_id=user_id, text="⚠️ <i>Please choose Normal or Join Request.</i>\n\n<b>SELECT YOUR MODE WHICH YOU WANT FOR THIS BELOW 👇</b>\n\n<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>", reply_markup=mode_kb)
                    track_fsub_msg(user_id, mode_prompt_msg.id)

            if not is_user_session_active(user_id, sess_token):
                return

            # Obtain or create appropriate invite link
            invite_client = target_client or client
            invite_link = None
            try:
                if chosen_mode == "request":
                    inv = await invite_client.create_chat_invite_link(chat_id, creates_join_request=True)
                    invite_link = inv.invite_link
                else:
                    chat_obj = await invite_client.get_chat(chat_id)
                    invite_link = chat_obj.invite_link
                    if not invite_link:
                        if chat_obj.username:
                            invite_link = f"https://t.me/{chat_obj.username}"
                        else:
                            inv = await invite_client.create_chat_invite_link(chat_id)
                            invite_link = inv.invite_link
            except Exception:
                if chat_username:
                    invite_link = f"https://t.me/{chat_username}"
                else:
                    try:
                        inv = await invite_client.export_chat_invite_link(chat_id)
                        invite_link = inv
                    except Exception:
                        invite_link = f"https://t.me/{chat_id}"

            # Save channel entry
            chs = list(r.get("fsub_channels", []))
            chs = [c for c in chs if (c.get("chat_id") if isinstance(c, dict) else c) != chat_id]
            chs.append({
                "chat_id": chat_id,
                "title": chat_title or f"Channel {len(chs)+1}",
                "username": chat_username,
                "mode": chosen_mode,
                "invite_link": invite_link
            })

            save_fn(fsub_channels=chs, fsub_enabled=True)
            if target_bid and mongo_db is not None:
                try:
                    mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_channels": chs, "fsub_enabled": True}}, upsert=True)
                except Exception:
                    pass
            r["fsub_channels"] = chs
            r["fsub_enabled"] = True
            clear_user_session(user_id)

            try:
                temp_msg = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                await temp_msg.delete()
            except Exception:
                pass

            succ_m = await client.send_message(
                chat_id=user_id,
                text=f"✨ <b>Successfully Added {chat_title or 'Channel'} As Your Force Sub Channel</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]]),
            )
            track_fsub_msg(user_id, succ_m.id)

        asyncio.create_task(_add_fsub_worker())
        return

    # 6. Force Subscribe Message Submenu
    if data == "cset_fsub_msg_menu":
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        buttons = [
            [InlineKeyboardButton("FORCE SUBSCRIBE TEXT", callback_data="cset_fsub_text_menu")],
            [InlineKeyboardButton("FORCE SUBSCRIBE PICTURE", callback_data="cset_fsub_pic_menu")],
            [InlineKeyboardButton("FORCE SUBSCRIBE FAKE BUTTON", callback_data="cset_fsub_fake_btn_menu")],
            [InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]
        ]
        return await edit_or_reply_fn(query, FSUB_MSG_DESC, reply_markup=InlineKeyboardMarkup(buttons))

    # 7. Force Subscribe Text Submenu
    if data == "cset_fsub_text_menu":
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        current_txt = r.get("fsub_text") or DEFAULT_FSUB_TEXT
        text_disp = (
            f"<b>TEXT - {current_txt}</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<code>{user_mention}</code> : <b>USER - NAME</b>\n\n"
            "<i>YOU CAN USE HTML STYLE FORMATTING IN TEXT</i>"
        )
        buttons = [
            [InlineKeyboardButton("SET FORCE SUBSCRIBE TEXT", callback_data="cset_fsub_set_text")],
            [InlineKeyboardButton("DEFAULT FORCE SUBSCRIBE TEXT", callback_data="cset_fsub_def_text")],
            [InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_msg_menu")]
        ]
        return await edit_or_reply_fn(query, text_disp, reply_markup=InlineKeyboardMarkup(buttons))

    # 8. Set Custom Force Subscribe Text
    if data == "cset_fsub_set_text":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "fsub_set_text")
        await query.answer()

        await cleanup_fsub_msgs(client, user_id)

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg_text = (
            "<b>SEND ME A FORCE SUBSCRIBE TEXT.</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<code>{user_mention}</code> : <b>USER - NAME</b>\n\n"
            "<i>YOU CAN USE HTML STYLE FORMATTING IN TEXT</i>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        prompt_msg = await client.send_message(chat_id=user_id, text=prompt_msg_text)
        track_fsub_msg(user_id, prompt_msg.id)

        async def _set_txt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_text_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            try:
                await prompt_msg.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            txt = (ans.text or "").strip()
            if txt == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_text_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return
            if not txt:
                m = await client.send_message(
                    chat_id=user_id,
                    text="⚠️ <b>Please send a valid text message.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_text_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return

            save_fn(fsub_text=txt)
            if target_bid and mongo_db is not None:
                try:
                    mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_text": txt}}, upsert=True)
                except Exception:
                    pass
            r["fsub_text"] = txt
            clear_user_session(user_id)

            succ_m = await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET FORCE SUBSCRIBE TEXT - </b>\n\n{txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_text_menu")]]),
            )
            track_fsub_msg(user_id, succ_m.id)

        asyncio.create_task(_set_txt_worker())
        return

    # 9. Default Force Subscribe Text
    if data == "cset_fsub_def_text":
        save_fn(fsub_text=None)
        if target_bid and mongo_db is not None:
            try:
                mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_text": None}}, upsert=True)
            except Exception:
                pass
        r["fsub_text"] = None
        await query.answer("✅ Default Force Subscribe text restored!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_text_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 10. Force Subscribe Picture Submenu
    if data == "cset_fsub_pic_menu":
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        has_pic = bool(r.get("fsub_pic"))
        spoiler = bool(r.get("fsub_pic_spoiler", False))
        invert = bool(r.get("fsub_pic_invert", False))

        pic_status_txt = "<b>ALREADY ADDED PICTURE...</b>" if has_pic else "<b>YOU DIDN'T ADDED ANY PICTURE...</b>"
        desc = (
            "<b>INVERT CAPTION:</b> IF ON THEN CAPTION SHOW ABOVE FORCE SUBSCRIBE MESSAGE PICTURE, IF OFF THEN CAPTION SHOWN BELOW FORCE SUBSCRIBE MESSAGE PICTURE AS NORMAL.\n\n"
            "<b>SPOILER ANIMATION:</b> IF ON THEN FORCE SUBSCRIBE MESSAGE PICTURE GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.\n"
            "--------------------------------------------------\n"
            f"{pic_status_txt}\n\n"
            f"<b>SPOILER -</b> {'✅' if spoiler else '❌'}\n"
            f"<b>INVERT CAPTION -</b> {'✅' if invert else '❌'}"
        )
        buttons = [
            [InlineKeyboardButton("SET FORCE SUBSCRIBE PIC", callback_data="cset_fsub_set_pic")],
            [InlineKeyboardButton("DELETE FORCE SUBSCRIBE PIC", callback_data="cset_fsub_del_pic")],
            [InlineKeyboardButton("VIEW FORCE SUBSCRIBE PIC", callback_data="cset_fsub_view_pic")],
            [InlineKeyboardButton(f"SPOILER - {'✅' if spoiler else '❌'}", callback_data="cset_fsub_tgl_spoiler")],
            [InlineKeyboardButton(f"INVERT CAPTION - {'✅' if invert else '❌'}", callback_data="cset_fsub_tgl_invert")],
            [InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_msg_menu")]
        ]
        return await edit_or_reply_fn(query, desc, reply_markup=InlineKeyboardMarkup(buttons))

    # 11. Set Picture
    if data == "cset_fsub_set_pic":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "fsub_set_pic")
        await query.answer()

        await cleanup_fsub_msgs(client, user_id)

        try:
            await query.message.delete()
        except Exception:
            pass

        prompt_msg_text = (
            "<b>SEND ME A PICTURE.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        prompt_msg = await client.send_message(chat_id=user_id, text=prompt_msg_text)
        track_fsub_msg(user_id, prompt_msg.id)

        async def _set_pic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Timeout. Process cancelled.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_pic_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            try:
                await ans.delete()
            except Exception:
                pass

            raw_text = (ans.text or ans.caption or "").strip()
            if raw_text == "/cancel":
                m = await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>Process Cancelled Successfully!</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_pic_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return

            photo_file_id = None
            if ans.photo:
                photo_file_id = ans.photo.file_id
            elif ans.document and ans.document.mime_type and "image" in ans.document.mime_type:
                photo_file_id = ans.document.file_id

            if not photo_file_id:
                m = await client.send_message(
                    chat_id=user_id,
                    text="⚠️ <b>Please send a valid picture file.</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_pic_menu")]])
                )
                track_fsub_msg(user_id, m.id)
                clear_user_session(user_id)
                return

            clear_user_session(user_id)
            save_fn(fsub_pic=photo_file_id)
            if target_bid and mongo_db is not None:
                try:
                    mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_pic": photo_file_id}}, upsert=True)
                except Exception:
                    pass
            r["fsub_pic"] = photo_file_id

            succ_m = await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_pic_menu")]]),
            )
            track_fsub_msg(user_id, succ_m.id)

        asyncio.create_task(_set_pic_worker())
        return

    # 12. Delete Picture
    if data == "cset_fsub_del_pic":
        save_fn(fsub_pic=None)
        if target_bid and mongo_db is not None:
            try:
                mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_pic": None}}, upsert=True)
            except Exception:
                pass
        r["fsub_pic"] = None
        await query.answer("✅ Picture deleted successfully!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_pic_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 13. View Picture
    if data == "cset_fsub_view_pic":
        pic = r.get("fsub_pic")
        if not pic:
            return await query.answer("❌ You didn't add any picture yet!", show_alert=True)
        await query.answer()
        try:
            return await client.send_photo(
                chat_id=user_id,
                photo=pic,
                caption="🖼️ <b>Force Subscribe Picture Preview</b>",
                has_spoiler=bool(r.get("fsub_pic_spoiler", False))
            )
        except Exception:
            return await query.answer("❌ Failed to load picture!", show_alert=True)

    # 14. Toggle Picture Spoiler
    if data == "cset_fsub_tgl_spoiler":
        new_sp = not bool(r.get("fsub_pic_spoiler", False))
        save_fn(fsub_pic_spoiler=new_sp)
        if target_bid and mongo_db is not None:
            try:
                mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_pic_spoiler": new_sp}}, upsert=True)
            except Exception:
                pass
        r["fsub_pic_spoiler"] = new_sp
        await query.answer(f"Spoiler {'Enabled ✅' if new_sp else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_pic_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 15. Toggle Invert Caption
    if data == "cset_fsub_tgl_invert":
        new_inv = not bool(r.get("fsub_pic_invert", False))
        save_fn(fsub_pic_invert=new_inv)
        if target_bid and mongo_db is not None:
            try:
                mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_pic_invert": new_inv}}, upsert=True)
            except Exception:
                pass
        r["fsub_pic_invert"] = new_inv
        await query.answer(f"Invert Caption {'Enabled ✅' if new_inv else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_pic_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 16. Fake Button Submenu
    if data == "cset_fsub_fake_btn_menu":
        current_mid = query.message.id if query.message else 0
        await cleanup_fsub_msgs(client, user_id, except_ids=[current_mid])

        fsub_buttons = r.get("fsub_buttons", [])
        has_btns = bool(fsub_buttons)

        buttons = []
        if not has_btns:
            buttons.append([InlineKeyboardButton("ADD BUTTON", callback_data="cset_fsub_btn_add")])
        else:
            buttons.append([
                InlineKeyboardButton("SEE BUTTON", callback_data="cset_fsub_btn_see"),
                InlineKeyboardButton("REMOVE BUTTON", callback_data="cset_fsub_btn_rem")
            ])
        buttons.append([InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_msg_menu")])
        return await edit_or_reply_fn(query, FSUB_BUTTON_DESC, reply_markup=InlineKeyboardMarkup(buttons))

    # 17. Add Fake Buttons (Interactive Builder)
    if data == "cset_fsub_btn_add":
        await query.answer()
        return await run_fsub_button_builder(client, user_id, save_fn, cancel_listeners_fn, prev_msg=query.message)

    # 18. See Fake Buttons Preview
    if data == "cset_fsub_btn_see":
        fsub_buttons = r.get("fsub_buttons", [])
        if not fsub_buttons:
            return await query.answer("❌ No buttons configured yet!", show_alert=True)
        preview_btns = []
        for r_item in fsub_buttons:
            row = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row.append(InlineKeyboardButton(f"{b['text']} ↗️", url=b.get('url', 'https://t.me')))
            elif isinstance(r_item, dict) and "text" in r_item:
                row.append(InlineKeyboardButton(f"{r_item['text']} ↗️", url=r_item.get('url', 'https://t.me')))
            if row:
                preview_btns.append(row)
        preview_btns.append([InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")])
        return await edit_or_reply_fn(
            query,
            "⚪ <b>FORCE SUBSCRIBE MESSAGE BUTTON PREVIEW:</b>\n\n<i>Here is how your custom fake buttons will look:</i>",
            reply_markup=InlineKeyboardMarkup(preview_btns)
        )

    # 19. Remove Fake Buttons
    if data == "cset_fsub_btn_rem":
        save_fn(fsub_buttons=[])
        if target_bid and mongo_db is not None:
            try:
                mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": {"fsub_buttons": []}}, upsert=True)
            except Exception:
                pass
        r["fsub_buttons"] = []
        await query.answer("✅ All custom buttons removed!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_fake_btn_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    return False
