# ♻️ AUTO DELETE SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session
from clone_plugins.users_api import parse_auto_delete_time, format_auto_delete_time


async def run_ad_button_builder(client, user_id, save_fn, cancel_listeners_fn, back_cb="cset_ad_btn", current_pic=None):
    cancel_listeners_fn(client, user_id, user_id)
    sess_token = start_user_session(user_id, "ad_btn_builder")
    rows = []
    row_idx = 1

    while is_user_session_active(user_id, sess_token):
        count_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("1️⃣ One Button"), KeyboardButton("2️⃣ Two Buttons")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        msg_text = (
            f"🚀 <b>ROW {row_idx}</b>\n\n"
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
                invalid_msg = (
                    "❌ <b>INVALID CHOICE</b>\n\n"
                    "<i>Please select an option using the keyboard.</i>"
                )
                await client.send_message(chat_id=user_id, text=invalid_msg, reply_markup=count_kb)

        if not is_user_session_active(user_id, sess_token):
            return

        row_buttons = []
        for b_i in range(1, btn_count + 1):
            btn_num = b_i if btn_count > 1 else 1

            # Step A: Button Text
            await client.send_message(
                chat_id=user_id,
                text=f"🔤 <b>BUTTON {btn_num}</b>\n\n<i>Send the button text.</i>\n\n<i>Maximum length: 64 characters</i>",
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
                f"🔗 <b>BUTTON {btn_num}</b>\n\n"
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
                    await client.send_message(chat_id=user_id, text="⚠️ <i>Invalid URL! It must start with http:// or https://. Send again:</i>")
                    continue
                b_url = u
                break

            if not is_user_session_active(user_id, sess_token):
                return

            # Step C: Button Style
            style_kb = ReplyKeyboardMarkup(
                [
                    [KeyboardButton("🔵 Primary"), KeyboardButton("⚪ Default")],
                    [KeyboardButton("🟢 Success"), KeyboardButton("🔴 Danger")]
                ],
                resize_keyboard=True, one_time_keyboard=True
            )
            await client.send_message(
                chat_id=user_id,
                text=f"🎨 <b>ROW {row_idx}</b>\n\n<i>Select a button style.</i>\n\n<i>Choose one of the options below.</i>",
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

            row_buttons.append({"text": b_text, "url": b_url, "style": b_style})

        rows.append({"buttons": row_buttons})

        # Step D: Add Another Row or Finish
        next_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Yes"), KeyboardButton("❌ No")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await client.send_message(
            chat_id=user_id,
            text="➕ <b>ADD NEW ROW</b>\n\n<i>Do you want to add another row?</i>",
            reply_markup=next_kb
        )

        finish = False
        while is_user_session_active(user_id, sess_token):
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            nxt = (ans.text or "").strip().lower()
            if nxt == "/cancel":
                await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            if "no" in nxt or "❌" in nxt or "finish" in nxt or "done" in nxt:
                finish = True
                break
            elif "yes" in nxt or "✅" in nxt or "add" in nxt:
                row_idx += 1
                break
            else:
                await client.send_message(chat_id=user_id, text="⚠️ <i>Please choose Yes or No from keyboard below.</i>", reply_markup=next_kb)

        if finish:
            break

    clear_user_session(user_id)
    save_fn(auto_delete_buttons=rows)

    try:
        await client.send_message(
            chat_id=user_id,
            text="✨ <b>Buttons updated successfully!</b>",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception:
        pass

    if current_pic:
        try:
            return await client.send_photo(
                chat_id=user_id,
                photo=current_pic,
                caption="<b>SUCCESSFULLY BUTTON ADDED</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
            )
        except Exception:
            pass

    await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
    )


async def handle_auto_delete_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    if not target_bid and ":" in str(data):
        last_p = str(data).split(":")[-1]
        if last_p.isdigit() and len(last_p) >= 6:
            target_bid = int(last_p)

    is_master = str(data).startswith("m_") or str(data).startswith("master_") or "master" in str(data) or (target_bid is not None)

    async def clean_show(txt, reply_markup=None):
        msg = getattr(query, "message", None) or query
        if msg and (getattr(msg, "photo", None) or getattr(msg, "media", None)):
            try:
                await msg.delete()
            except Exception:
                pass
            return await client.send_message(chat_id=user_id, text=txt, reply_markup=reply_markup)
        return await edit_or_reply_fn(query, txt, reply_markup=reply_markup)

    # 1. Main Auto Delete Menu
    if data in ("master_auto_delete_menu", "cset_autodelete", "cset_auto_delete_menu") or str(data).startswith(("master_auto_delete_menu", "cset_autodelete", "cset_auto_delete_menu")):
        ad_on = bool(r.get("auto_delete_enabled", False))
        ad_time = int(r.get("auto_delete_time", 600))
        ad_again = bool(r.get("auto_delete_get_again", True))
        status_txt = "ON ✅" if ad_on else "OFF ❌"
        time_txt = format_auto_delete_time(ad_time)
        text = (
            "♻️ <b>MESSAGE AUTO DELETE:</b>\n\n"
            "<b>MESSAGE AUTO DELETE: IF TIME IS SET THEN BOT AUTOMATICALLY DELETE THE GIVEN MESSAGE. THIS WILL PREVENT BOT FROM GETTING BAN OR COPYRIGHT.</b>\n\n"
            f"<b>AUTO DELETE - {status_txt}</b>\n\n"
            f"<b>DELETE TIME - {time_txt.upper()}</b>"
        )
        tgl_btn = "OFF AUTO DELETE" if ad_on else "ON AUTO DELETE"
        again_btn = "GET FILE AGAIN BUTTON - ✅" if ad_again else "GET FILE AGAIN BUTTON - ❌"
        back_cb = f"manage_clone:{target_bid}" if target_bid else ("settings" if is_master else "clone_my_clone_info")
        return await clean_show(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TIME", callback_data="m_set_ad_custom" if is_master else "cset_set_ad_time")],
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_ad" if is_master else "cset_tgl_ad")],
            [InlineKeyboardButton("AUTO DELETE MESSAGE", callback_data="m_ad_msg_menu" if is_master else "cset_ad_msg_menu")],
            [InlineKeyboardButton(again_btn, callback_data="m_tgl_ad_again" if is_master else "cset_tgl_ad_again")],
            [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
        ]))

    # 2. Toggle Auto Delete ON / OFF
    if data in ("m_tgl_ad", "cset_tgl_ad", "cset_autodelete_toggle") or str(data).startswith(("m_tgl_ad", "cset_tgl_ad", "cset_autodelete_toggle")):
        new_s = not bool(r.get("auto_delete_enabled", False))
        save_fn(auto_delete_enabled=new_s)
        r["auto_delete_enabled"] = new_s
        await query.answer(f"Auto delete {'Enabled' if new_s else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu" if is_master else "cset_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 3. Toggle Get File Again Button
    if data in ("m_tgl_ad_again", "cset_tgl_ad_again") or str(data).startswith(("m_tgl_ad_again", "cset_tgl_ad_again")):
        new_ag = not bool(r.get("auto_delete_get_again", True))
        save_fn(auto_delete_get_again=new_ag)
        r["auto_delete_get_again"] = new_ag
        await query.answer(f"Get file again button {'Enabled' if new_ag else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu" if is_master else "cset_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 4. Set Time (Seconds, Minutes, Hours, Days)
    if data in ("m_set_ad_custom", "cset_set_ad_time") or str(data).startswith(("m_set_ad_custom", "cset_set_ad_time")):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_ad_time")
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A TIME IN LIKE THIS - 1h OR 15m</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
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
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                menu_cb = "master_auto_delete_menu" if is_master else "cset_auto_delete_menu"
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]]))
                return
            sec = parse_auto_delete_time(t_txt)
            if not sec or sec <= 0:
                await client.send_message(user_id, "❌ <b>Invalid time format. Example: 5s, 10s, 1m, 2h, 1d.</b>")
                clear_user_session(user_id)
                return
            save_fn(auto_delete_enabled=True, auto_delete_time=sec, auto_delete_minutes=max(1, sec // 60))
            r["auto_delete_enabled"] = True
            r["auto_delete_time"] = sec
            clear_user_session(user_id)
            time_str = format_auto_delete_time(sec)
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            menu_cb = "master_auto_delete_menu" if is_master else "cset_auto_delete_menu"
            await client.send_message(
                user_id,
                f"🧭 <b>SUCCESSFULLY SET DELETE TIME - {time_str}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=menu_cb)]])
            )
        asyncio.create_task(_ad_worker())
        return

    # 5. AUTO DELETE MESSAGE Hub (Text, Picture, Button)
    if data in ("m_ad_msg_menu", "cset_ad_msg_menu") or str(data).startswith(("m_ad_msg_menu", "cset_ad_msg_menu")):
        text = (
            "📝 <b>AUTO DELETE MESSAGE:</b>\n\n"
            "<b>AUTO DELETE MESSAGE: YOU CAN CUSTOMISE YOUR CLONE BOT AUTO DELETE MESSAGE ANY WAY YOU LIKE.</b>"
        )
        back_cb = "master_auto_delete_menu" if is_master else "cset_auto_delete_menu"
        return await clean_show(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("AUTO DELETE TEXT", callback_data="m_ad_text" if is_master else "cset_ad_text")],
                [InlineKeyboardButton("AUTO DELETE PICTURE", callback_data="m_ad_pic" if is_master else "cset_ad_pic")],
                [InlineKeyboardButton("AUTO DELETE BUTTON", callback_data="m_ad_btn" if is_master else "cset_ad_btn")],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    # 6. AUTO DELETE TEXT Menu
    if data in ("m_ad_text", "cset_ad_text") or str(data).startswith(("m_ad_text", "cset_ad_text")):
        ad_txt = r.get("auto_delete_text") or "{user_mention} This message will be deleted in {time}"
        text = (
            "📝 <b>AUTO DELETE TEXT:</b>\n\n"
            f"<b>TEXT -</b> {ad_txt}\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n"
            "<code>{user_mention}</code> : USER - NAME\n"
            "<code>{time}</code> : AUTO DELETE TIME\n\n"
            "<i>YOU CAN USE HTML STYLE FORMATTING IN TEXT</i>"
        )
        back_cb = "m_ad_msg_menu" if is_master else "cset_ad_msg_menu"
        return await clean_show(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("SET AUTO DELETE TEXT", callback_data="m_ad_set_txt" if is_master else "cset_ad_set_txt"),
                    InlineKeyboardButton("DEFAULT AUTO DELETE TEXT", callback_data="m_ad_def_txt" if is_master else "cset_ad_def_txt")
                ],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    # 7. Set Auto Delete Text
    if data in ("m_ad_set_txt", "cset_ad_set_txt") or str(data).startswith(("m_ad_set_txt", "cset_ad_set_txt")):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_ad_text")
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A AUTO DELETE TEXT.</b>\n\n"
                "<b>AVAILABLE FILLINGS:</b>\n"
                "<code>{user_mention}</code> : USER - NAME\n"
                "<code>{time}</code> : AUTO DELETE TIME\n\n"
                "<i>YOU CAN USE HTML STYLE FORMATTING IN TEXT</i>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
        )
        async def _ad_txt_worker():
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
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                back_cb = "m_ad_text" if is_master else "cset_ad_text"
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]]))
                return
            if not t_txt:
                await client.send_message(user_id, "❌ <b>Invalid text.</b>")
                clear_user_session(user_id)
                return
            save_fn(auto_delete_text=t_txt)
            r["auto_delete_text"] = t_txt
            clear_user_session(user_id)
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            back_cb = "m_ad_text" if is_master else "cset_ad_text"
            await client.send_message(
                user_id,
                f"<b>SUCCESSFULLY SET AUTO DELETE - TEXT -</b>\n{t_txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
            )
        asyncio.create_task(_ad_txt_worker())
        return

    # 8. Default Auto Delete Text
    if data in ("m_ad_def_txt", "cset_ad_def_txt") or str(data).startswith(("m_ad_def_txt", "cset_ad_def_txt")):
        save_fn(auto_delete_text="")
        r["auto_delete_text"] = ""
        await query.answer("Auto delete text reset to default!")
        return await handle_auto_delete_callbacks(client, query, "m_ad_text" if is_master else "cset_ad_text", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 9. AUTO DELETE PICTURE Menu
    if data in ("m_ad_pic", "cset_ad_pic") or str(data).startswith(("m_ad_pic", "cset_ad_pic")):
        ad_pic = r.get("auto_delete_pic")
        has_pic = bool(ad_pic)
        spoiler = bool(r.get("auto_delete_pic_spoiler", False))
        invert = bool(r.get("auto_delete_pic_invert_caption", False))
        pic_status = "ALREADY ADDED PICTURE..." if has_pic else "NOT ADDED ANY PICTURE..."
        spoil_str = "✅" if spoiler else "❌"
        invert_str = "✅" if invert else "❌"

        text = (
            "<b>PICTURE, IF OFF THEN CAPTION SHOWN BELOW AUTO DELETE MESSAGE PICTURE AS NORMAL.</b>\n\n"
            "<b>SPOILER ANIMATION: IF ON THEN AUTO DELETE MESSAGE PICTURE GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.</b>\n\n"
            f"<b>{pic_status}</b>\n\n"
            f"<b>SPOILER -</b> {spoil_str}\n\n"
            f"<b>INVERT CAPTION -</b> {invert_str}"
        )
        back_cb = "m_ad_msg_menu" if is_master else "cset_ad_msg_menu"
        return await clean_show(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET AUTO DELETE PIC", callback_data="m_ad_set_pic" if is_master else "cset_ad_set_pic")],
                [InlineKeyboardButton("DELETE AUTO DELETE PIC", callback_data="m_ad_del_pic" if is_master else "cset_ad_del_pic")],
                [InlineKeyboardButton("VIEW AUTO DELETE PIC", callback_data="m_ad_view_pic" if is_master else "cset_ad_view_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoil_str}", callback_data="m_ad_tgl_spoil" if is_master else "cset_ad_tgl_spoil")],
                [InlineKeyboardButton(f"INVERT CAPTION - {invert_str}", callback_data="m_ad_tgl_invert" if is_master else "cset_ad_tgl_invert")],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        )

    # 10. Set Auto Delete Pic
    if data in ("m_ad_set_pic", "cset_ad_set_pic") or str(data).startswith(("m_ad_set_pic", "cset_ad_set_pic")):
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_ad_pic")
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        prompt_msg = await client.send_message(
            chat_id=user_id,
            text=(
                "<b>SEND ME A PICTURE.</b>\n\n"
                "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>"
            )
        )
        async def _ad_pic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if ans.text and ans.text.strip() == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                clear_user_session(user_id)
                back_cb = "m_ad_pic" if is_master else "cset_ad_pic"
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]]))
                return
            photo = ans.photo or (ans.document if ans.document and ans.document.mime_type and ans.document.mime_type.startswith("image/") else None)
            if not photo:
                await client.send_message(user_id, "❌ <b>Please send a valid picture/photo.</b>")
                clear_user_session(user_id)
                return
            file_id = photo.file_id
            save_fn(auto_delete_pic=file_id)
            r["auto_delete_pic"] = file_id
            clear_user_session(user_id)
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            back_cb = "m_ad_pic" if is_master else "cset_ad_pic"
            try:
                await client.send_photo(
                    chat_id=user_id,
                    photo=file_id,
                    caption="<b>SUCCESSFULLY PICTURE SET</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
                )
            except Exception:
                await client.send_message(
                    user_id,
                    "<b>SUCCESSFULLY PICTURE SET</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
                )
        asyncio.create_task(_ad_pic_worker())
        return

    # 11. Delete Auto Delete Pic
    if data in ("m_ad_del_pic", "cset_ad_del_pic") or str(data).startswith(("m_ad_del_pic", "cset_ad_del_pic")):
        save_fn(auto_delete_pic=None)
        r["auto_delete_pic"] = None
        await query.answer("Picture deleted successfully!")
        return await handle_auto_delete_callbacks(client, query, "m_ad_pic" if is_master else "cset_ad_pic", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 12. View Auto Delete Pic
    if data in ("m_ad_view_pic", "cset_ad_view_pic") or str(data).startswith(("m_ad_view_pic", "cset_ad_view_pic")):
        ad_pic = r.get("auto_delete_pic")
        if not ad_pic:
            return await query.answer("No picture set!", show_alert=True)
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        back_cb = "m_ad_pic" if is_master else "cset_ad_pic"
        try:
            await client.send_photo(
                chat_id=user_id,
                photo=ad_pic,
                caption="<b>🖼️ CURRENT AUTO DELETE PICTURE</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
            )
        except Exception:
            await client.send_message(
                chat_id=user_id,
                text="❌ Unable to display picture.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
            )
        return

    # 13. Toggle Spoiler
    if data in ("m_ad_tgl_spoil", "cset_ad_tgl_spoil") or str(data).startswith(("m_ad_tgl_spoil", "cset_ad_tgl_spoil")):
        new_sp = not bool(r.get("auto_delete_pic_spoiler", False))
        save_fn(auto_delete_pic_spoiler=new_sp)
        r["auto_delete_pic_spoiler"] = new_sp
        await query.answer(f"Spoiler {'Enabled' if new_sp else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "m_ad_pic" if is_master else "cset_ad_pic", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 14. Toggle Invert Caption
    if data in ("m_ad_tgl_invert", "cset_ad_tgl_invert") or str(data).startswith(("m_ad_tgl_invert", "cset_ad_tgl_invert")):
        new_inv = not bool(r.get("auto_delete_pic_invert_caption", False))
        save_fn(auto_delete_pic_invert_caption=new_inv)
        r["auto_delete_pic_invert_caption"] = new_inv
        await query.answer(f"Invert caption {'Enabled' if new_inv else 'Disabled'}!")
        return await handle_auto_delete_callbacks(client, query, "m_ad_pic" if is_master else "cset_ad_pic", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)

    # 15. AUTO DELETE BUTTON Menu
    if data in ("m_ad_btn", "cset_ad_btn") or str(data).startswith(("m_ad_btn", "cset_ad_btn")):
        ad_btns = r.get("auto_delete_buttons", [])
        has_btns = bool(ad_btns)
        text = (
            "🔘 <b>AUTO DELETE MESSAGE BUTTON:</b>\n\n"
            "<b>CREATE CUSTOM URL BUTTONS FOR YOUR MESSAGE.</b>\n\n"
            "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
            "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
            "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
            "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>"
        )
        back_cb = "m_ad_msg_menu" if is_master else "cset_ad_msg_menu"
        if has_btns:
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("SEE BUTTON", callback_data="m_ad_btn_see" if is_master else "cset_ad_btn_see"),
                    InlineKeyboardButton("REMOVE BUTTON", callback_data="m_ad_btn_rem" if is_master else "cset_ad_btn_rem")
                ],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        else:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("ADD BUTTON", callback_data="m_ad_btn_add" if is_master else "cset_ad_btn_add")],
                [InlineKeyboardButton("‹ BACK", callback_data=back_cb)]
            ])
        return await clean_show(text, reply_markup=markup)

    # 16. Add Button Builder
    if data in ("m_ad_btn_add", "cset_ad_btn_add") or str(data).startswith(("m_ad_btn_add", "cset_ad_btn_add")):
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        back_cb = "m_ad_btn" if is_master else "cset_ad_btn"
        current_pic = r.get("auto_delete_pic")
        asyncio.create_task(run_ad_button_builder(client, user_id, save_fn, cancel_listeners_fn, back_cb=back_cb, current_pic=current_pic))
        return

    # 17. Remove Button
    if data in ("m_ad_btn_rem", "cset_ad_btn_rem") or str(data).startswith(("m_ad_btn_rem", "cset_ad_btn_rem")):
        save_fn(auto_delete_buttons=[])
        r["auto_delete_buttons"] = []
        await query.answer("Buttons deleted!")
        back_cb = "m_ad_btn" if is_master else "cset_ad_btn"
        return await clean_show(
            "<b>SUCCESSFULLY BUTTON DELETED</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
        )

    # 18. See Button
    if data in ("m_ad_btn_see", "cset_ad_btn_see") or str(data).startswith(("m_ad_btn_see", "cset_ad_btn_see")):
        ad_btns = r.get("auto_delete_buttons", [])
        rows = []
        for r_item in ad_btns:
            row_btns = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row_btns.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            elif isinstance(r_item, list):
                for b in r_item:
                    if isinstance(b, dict) and b.get("text"):
                        row_btns.append(InlineKeyboardButton(b["text"], url=b.get("url", "https://t.me")))
            if row_btns:
                rows.append(row_btns)
        back_cb = "m_ad_btn" if is_master else "cset_ad_btn"
        rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_cb)])
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        current_pic = r.get("auto_delete_pic")
        if current_pic:
            try:
                return await client.send_photo(
                    chat_id=user_id,
                    photo=current_pic,
                    caption="<b>🔘 SAMPLE BUTTON PREVIEW</b>",
                    reply_markup=InlineKeyboardMarkup(rows)
                )
            except Exception:
                pass
        return await client.send_message(
            chat_id=user_id,
            text="<b>🔘 SAMPLE BUTTON PREVIEW</b>",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    # 19. Preset auto delete setters
    if data.startswith("m_set_ad:") or data.startswith("cset_autodelete_set:") or data.startswith("cset_set_ad:"):
        sec = int(data.split(":")[1])
        save_fn(auto_delete_enabled=True, auto_delete_time=sec, auto_delete_minutes=max(1, sec // 60))
        r["auto_delete_enabled"] = True
        r["auto_delete_time"] = sec
        time_str = format_auto_delete_time(sec)
        await query.answer(f"Auto delete set to {time_str}!")
        return await handle_auto_delete_callbacks(client, query, "master_auto_delete_menu" if is_master else "cset_auto_delete_menu", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=target_bid)


