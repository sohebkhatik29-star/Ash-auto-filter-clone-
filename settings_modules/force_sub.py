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

async def run_fsub_button_builder(client, user_id, save_fn, cancel_listeners_fn):
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
            "<i>Please choose an option using the keyboard below.</i>"
        )
        await client.send_message(chat_id=user_id, text=msg_text, reply_markup=count_kb)

        btn_count = 0
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            if "1" in txt or "One" in txt:
                btn_count = 1
                break
            elif "2" in txt or "Two" in txt:
                btn_count = 2
                break
            else:
                invalid_msg = "❌ <b>INVALID CHOICE</b>\n\n<i>Please select 1 or 2 using the keyboard.</i>"
                await client.send_message(chat_id=user_id, text=invalid_msg, reply_markup=count_kb)

        if not is_user_session_active(user_id, sess_token):
            return

        row_buttons = []
        for b_i in range(1, btn_count + 1):
            btn_num = b_i if btn_count > 1 else 1

            # Step A: Button Text
            await client.send_message(
                chat_id=user_id,
                text=f"🔤 <b>BUTTON {btn_num} ❞</b>\n\n<i>Send the button text.</i>\n\n<i>Maximum length: 64 characters</i>",
                reply_markup=ReplyKeyboardRemove()
            )
            b_text = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                t = (ans.text or "").strip()
                if t == "/cancel":
                    await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                if not t:
                    await client.send_message(chat_id=user_id, text="⚠️ <i>Please send valid text.</i>")
                    continue
                if len(t) > 64:
                    await client.send_message(chat_id=user_id, text="⚠️ <i>Button text exceeds 64 characters. Send again:</i>")
                    continue
                b_text = t
                break

            if not is_user_session_active(user_id, sess_token):
                return

            # Step B: Button URL
            url_prompt = (
                f"🔗 <b>BUTTON {btn_num} ❞</b>\n\n"
                "<i>Send the button URL.</i>\n\n"
                "<i>Examples:</i>\n"
                "<code>https://t.me/vj_botz</code>\n"
                "<code>https://google.com</code>"
            )
            await client.send_message(chat_id=user_id, text=url_prompt)
            b_url = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                u = (ans.text or "").strip()
                if u == "/cancel":
                    await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                if not (u.startswith("http://") or u.startswith("https://") or u.startswith("tg://")):
                    await client.send_message(chat_id=user_id, text="⚠️ <i>Invalid URL! Must start with http://, https:// or tg://. Send again:</i>")
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
        await client.send_message(
            chat_id=user_id,
            text=f"🪧 <b>ROW {row_idx} ❞</b>\n\n<i>Select a button style.</i>\n\n<i>Choose one of the options below.</i>",
            reply_markup=style_kb
        )
        b_style = "primary"
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            st = (ans.text or "").strip().lower()
            if st == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
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
        await client.send_message(
            chat_id=user_id,
            text="➕ <b>ADD NEW ROW ❞</b>\n\n<i>Do you want to add another row?</i>",
            reply_markup=add_more_kb
        )
        add_more = False
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            ans_txt = (ans.text or "").strip()
            if ans_txt == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
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
                await client.send_message(chat_id=user_id, text="⚠️ <i>Please choose Yes or No.</i>", reply_markup=add_more_kb)

        if not is_user_session_active(user_id, sess_token):
            return

        if not add_more:
            break

    clear_user_session(user_id)
    save_fn(fsub_buttons=rows)
    await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_fake_btn_menu")]]),
    )


# ----------------- MAIN CALLBACK HANDLER ----------------- #

async def handle_fsub_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, *args, **kwargs):
    # 1. Main Force Subscribe Settings Menu
    if data in ("master_fsub_menu", "cset_fsub_menu", "cset_fsub_main"):
        fsub_on = bool(r.get("fsub_enabled", False))
        channels = r.get("fsub_channels", [])
        
        status_line = f"<b>FORCE SUBSCRIBE - {'ON ✅' if fsub_on else 'OFF ❌'}</b>"
        text = f"{FSUB_MAIN_DESC}\n{status_line}"

        buttons = []
        # Channel item buttons
        for idx, ch in enumerate(channels):
            if isinstance(ch, dict):
                title = ch.get("title") or f"Channel {idx+1}"
                buttons.append([InlineKeyboardButton(f"{title}", callback_data=f"cset_fsub_ch:{idx}")])
            else:
                buttons.append([InlineKeyboardButton(f"Channel: {ch}", callback_data=f"cset_fsub_ch:{idx}")])

        buttons.append([InlineKeyboardButton("➕ ADD CHANNEL ➕", callback_data="cset_fsub_add")])
        if fsub_on:
            buttons.append([InlineKeyboardButton("OFF FORCE SUBSCRIBE", callback_data="cset_fsub_toggle")])
        else:
            buttons.append([InlineKeyboardButton("ON FORCE SUBSCRIBE", callback_data="cset_fsub_toggle")])
            
        buttons.append([InlineKeyboardButton("FORCE SUBSCRIBE MESSAGE", callback_data="cset_fsub_msg_menu")])
        is_master = data.startswith("master_") or r.get("type") == "master_config"
        back_cb = "settings" if is_master else "clone_my_clone_info"
        buttons.append([InlineKeyboardButton("≼ BACK", callback_data=back_cb)])

        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup(buttons))

    # 2. Toggle FSub Status
    if data in ("m_tgl_fsub", "cset_fsub_toggle"):
        new_status = not bool(r.get("fsub_enabled", False))
        save_fn(fsub_enabled=new_status)
        r["fsub_enabled"] = new_status
        await query.answer(f"Force Subscribe {'Enabled ✅' if new_status else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 3. View / Manage Channel
    if data.startswith("cset_fsub_ch:"):
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
            save_fn(fsub_channels=channels)
            r["fsub_channels"] = channels
            await query.answer("✅ Channel deleted successfully!")
        else:
            await query.answer("Channel not found!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 5. Add Channel Flow
    if data in ("m_add_fsub", "cset_fsub_add"):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "fsub_add_ch")
        await query.answer()

        prompt_msg = (
            "<b>( SET CHANNEL )</b>\n\n"
            "<b>FORWARD A MESSAGE FROM YOUR FORCE SUBSCRIBE CHANNEL WITH FORWARD TAG AND MAKE ME ADMIN IN THAT CHANNEL WITH FULL RIGHTS</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        await client.send_message(chat_id=user_id, text=prompt_msg)

        async def _add_fsub_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>")
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
                await client.send_message(user_id, "❌ <b>Please forward a message directly from the channel!</b>")
                clear_user_session(user_id)
                return

            # Verify admin permissions
            me = client.me or (await client.get_me())
            try:
                member = await client.get_chat_member(chat_id, me.id)
                if member.status not in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                    err_msg = (
                        "⚠️ <b>SOMETHING WENT WRONG</b>\n\n"
                        "Telegram says: [403 CHAT_WRITE_FORBIDDEN] - You don't have rights to send messages in this chat. (caused by \"messages.ExportChatInvite\")"
                    )
                    clear_user_session(user_id)
                    return await client.send_message(user_id, err_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]]))
            except Exception as e:
                err_str = str(e)
                err_msg = (
                    "⚠️ <b>SOMETHING WENT WRONG</b>\n\n"
                    f"Telegram says: [{err_str}] - Make sure I am an admin in the channel with full rights!"
                )
                clear_user_session(user_id)
                return await client.send_message(user_id, err_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]]))

            # Prompt mode: Normal or Join Request
            mode_kb = ReplyKeyboardMarkup(
                [[KeyboardButton("Normal"), KeyboardButton("Join Request")]],
                resize_keyboard=True, one_time_keyboard=True
            )
            await client.send_message(
                chat_id=user_id,
                text="<b>SELECT YOUR MODE WHICH YOU WANT FOR THIS BELOW 👇</b>",
                reply_markup=mode_kb
            )

            chosen_mode = "normal"
            while is_user_session_active(user_id, sess_token):
                try:
                    m_ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                m_txt = (m_ans.text or "").strip().lower()
                if m_txt == "/cancel":
                    await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                if "request" in m_txt:
                    chosen_mode = "request"
                    break
                elif "normal" in m_txt:
                    chosen_mode = "normal"
                    break
                else:
                    await client.send_message(chat_id=user_id, text="⚠️ <i>Please choose Normal or Join Request.</i>", reply_markup=mode_kb)

            if not is_user_session_active(user_id, sess_token):
                return

            # Obtain or create appropriate invite link
            invite_link = None
            try:
                if chosen_mode == "request":
                    inv = await client.create_chat_invite_link(chat_id, creates_join_request=True)
                    invite_link = inv.invite_link
                else:
                    chat_obj = await client.get_chat(chat_id)
                    invite_link = chat_obj.invite_link
                    if not invite_link:
                        if chat_obj.username:
                            invite_link = f"https://t.me/{chat_obj.username}"
                        else:
                            inv = await client.create_chat_invite_link(chat_id)
                            invite_link = inv.invite_link
            except Exception:
                if chat_username:
                    invite_link = f"https://t.me/{chat_username}"
                else:
                    try:
                        inv = await client.export_chat_invite_link(chat_id)
                        invite_link = inv
                    except Exception:
                        invite_link = f"https://t.me/{chat_id}"

            # Save channel entry
            chs = list(r.get("fsub_channels", []))
            # Remove duplicate of same chat_id if exists
            chs = [c for c in chs if (c.get("chat_id") if isinstance(c, dict) else c) != chat_id]
            chs.append({
                "chat_id": chat_id,
                "title": chat_title or f"Channel {len(chs)+1}",
                "username": chat_username,
                "mode": chosen_mode,
                "invite_link": invite_link
            })

            save_fn(fsub_channels=chs, fsub_enabled=True)
            r["fsub_channels"] = chs
            r["fsub_enabled"] = True
            clear_user_session(user_id)

            await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY UPDATED</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]]),
            )
            # Remove custom reply keyboard
            try:
                temp_msg = await client.send_message(chat_id=user_id, text=".", reply_markup=ReplyKeyboardRemove())
                await temp_msg.delete()
            except Exception:
                pass

        asyncio.create_task(_add_fsub_worker())
        return

    # 6. Force Subscribe Message Submenu
    if data == "cset_fsub_msg_menu":
        buttons = [
            [InlineKeyboardButton("FORCE SUBSCRIBE TEXT", callback_data="cset_fsub_text_menu")],
            [InlineKeyboardButton("FORCE SUBSCRIBE PICTURE", callback_data="cset_fsub_pic_menu")],
            [InlineKeyboardButton("FORCE SUBSCRIBE FAKE BUTTON", callback_data="cset_fsub_fake_btn_menu")],
            [InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_menu")]
        ]
        return await edit_or_reply_fn(query, FSUB_MSG_DESC, reply_markup=InlineKeyboardMarkup(buttons))

    # 7. Force Subscribe Text Submenu
    if data == "cset_fsub_text_menu":
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

        prompt_msg = (
            "<b>SEND ME A FORCE SUBSCRIBE TEXT.</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<code>{user_mention}</code> : <b>USER - NAME</b>\n\n"
            "<i>YOU CAN USE HTML STYLE FORMATTING IN TEXT</i>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        await client.send_message(chat_id=user_id, text=prompt_msg)

        async def _set_txt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            if not txt:
                await client.send_message(chat_id=user_id, text="⚠️ <b>Please send a valid text message.</b>")
                clear_user_session(user_id)
                return

            save_fn(fsub_text=txt)
            r["fsub_text"] = txt
            clear_user_session(user_id)

            await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET FORCE SUBSCRIBE TEXT - </b>\n\n{txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_text_menu")]])
            )

        asyncio.create_task(_set_txt_worker())
        return

    # 9. Default Force Subscribe Text
    if data == "cset_fsub_def_text":
        save_fn(fsub_text=None)
        r["fsub_text"] = None
        await query.answer("✅ Default Force Subscribe text restored!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_text_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 10. Force Subscribe Picture Submenu
    if data == "cset_fsub_pic_menu":
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

        prompt_msg = (
            "<b>SEND ME A PICTURE.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS</b>"
        )
        await client.send_message(chat_id=user_id, text=prompt_msg)

        async def _set_pic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if ans.text and ans.text.strip() == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return

            photo_file_id = None
            if ans.photo:
                photo_file_id = ans.photo.file_id
            elif ans.document and ans.document.mime_type and "image" in ans.document.mime_type:
                photo_file_id = ans.document.file_id

            if not photo_file_id:
                await client.send_message(chat_id=user_id, text="⚠️ <b>Please send a valid picture file.</b>")
                clear_user_session(user_id)
                return

            dl_msg = await client.send_message(chat_id=user_id, text="<b>DOWNLOADING...</b>")
            save_fn(fsub_pic=photo_file_id)
            r["fsub_pic"] = photo_file_id
            clear_user_session(user_id)

            await dl_msg.edit_text(
                "<b>SUCCESSFULLY PICTURE SET</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("≼ BACK", callback_data="cset_fsub_pic_menu")]])
            )

        asyncio.create_task(_set_pic_worker())
        return

    # 12. Delete Picture
    if data == "cset_fsub_del_pic":
        save_fn(fsub_pic=None)
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
        r["fsub_pic_spoiler"] = new_sp
        await query.answer(f"Spoiler {'Enabled ✅' if new_sp else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_pic_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 15. Toggle Invert Caption
    if data == "cset_fsub_tgl_invert":
        new_inv = not bool(r.get("fsub_pic_invert", False))
        save_fn(fsub_pic_invert=new_inv)
        r["fsub_pic_invert"] = new_inv
        await query.answer(f"Invert Caption {'Enabled ✅' if new_inv else 'Disabled ❌'}")
        return await handle_fsub_callbacks(client, query, "cset_fsub_pic_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 16. Fake Button Submenu
    if data == "cset_fsub_fake_btn_menu":
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

    # 17. Add Fake Buttons
    if data == "cset_fsub_btn_add":
        await query.answer()
        asyncio.create_task(run_fsub_button_builder(client, user_id, save_fn, cancel_listeners_fn))
        return

    # 18. See Fake Buttons Preview
    if data == "cset_fsub_btn_see":
        fsub_buttons = r.get("fsub_buttons", [])
        if not fsub_buttons:
            return await query.answer("❌ No buttons configured!", show_alert=True)
        await query.answer()
        preview_rows = []
        for r_item in fsub_buttons:
            row = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            if row:
                preview_rows.append(row)
        preview_markup = InlineKeyboardMarkup(preview_rows) if preview_rows else None
        return await client.send_message(
            chat_id=user_id,
            text="👁️ <b>Force Subscribe Buttons Preview:</b>",
            reply_markup=preview_markup
        )

    # 19. Remove Fake Buttons
    if data == "cset_fsub_btn_rem":
        save_fn(fsub_buttons=[])
        r["fsub_buttons"] = []
        await query.answer("✅ Force Subscribe buttons removed!")
        return await handle_fsub_callbacks(client, query, "cset_fsub_fake_btn_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)
