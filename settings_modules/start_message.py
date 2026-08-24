# 📝 START MESSAGE SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session


async def run_start_button_builder(client, user_id, save_fn, cancel_listeners_fn):
    cancel_listeners_fn(client, user_id, user_id)
    sess_token = start_user_session(user_id, "start_btn_builder")
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
    save_fn(start_buttons=rows)

    await client.send_message(
        chat_id=user_id,
        text="✨ <b>Buttons updated successfully!</b>",
        reply_markup=ReplyKeyboardRemove()
    )
    await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_btn")]])
    )


async def handle_start_message_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    # 1. Main START MESSAGE Hub
    if data == "cset_start_msg_menu":
        text = (
            "📝 <b>START MESSAGE:</b>\n\n"
            "<b>START MESSAGE: WHEN USER GIVE START COMMAND OR START THE BOT THEN BOT REPLY START MESSAGE. IN START MESSAGE BOT OWNER CAN SET START MESSAGE TEXT, PICTURE AND BUTTON.</b>"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("START TEXT", callback_data="cset_start_text")],
                [InlineKeyboardButton("START PICTURE", callback_data="cset_start_pic")],
                [InlineKeyboardButton("START BUTTON", callback_data="cset_start_btn")],
                [InlineKeyboardButton("🪧 BACK", callback_data="clone_my_clone_info")]
            ])
        )

    # 2. START TEXT Screen
    if data == "cset_start_text":
        st_txt = r.get("start_text") or f"Hii {query.from_user.mention} {client.me.mention} hu kya naam he teraa"
        text = (
            "📝 <b>START TEXT:</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n"
            "{mention} - USER - NAME MENTION\n"
            "{bot_mention} - BOT - NAME MENTION\n\n"
            f"<b>TEXT -</b> {st_txt}"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET TEXT", callback_data="cset_set_start_text"), InlineKeyboardButton("DEFAULT TEXT", callback_data="cset_def_start_text")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_text":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_start_text")
        await query.answer()
        await edit_or_reply_fn(
            query,
            "<b>SEND ME A START TEXT.</b>\n\n<b>AVAILABLE FILLINGS:</b>\n{mention} - USER - NAME MENTION\n{bot_mention} - BOT - NAME MENTION\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
        )
        async def _stxt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            t_val = (ans.text or "").strip()
            clear_user_session(user_id)
            if t_val == "/cancel":
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]]) )
            save_fn(start_text=t_val)
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET START TEXT -</b>\n\n{t_val}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
            )
        asyncio.create_task(_stxt_worker())
        return

    if data == "cset_def_start_text":
        save_fn(start_text=None)
        await query.answer("Reset to default start text!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY SET TO DEFAULT START TEXT.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_text")]])
        )

    # 3. START PICTURE Screen
    if data == "cset_start_pic":
        pic = r.get("start_pic")
        spoiler = bool(r.get("start_pic_spoiler", False))
        spoiler_status = "✅" if spoiler else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if pic else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "🖼️ <b>START PICTURE:</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER EFFECT - </b>{spoiler_status}"
        )
        return await edit_or_reply_fn(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PICTURE", callback_data="cset_set_start_pic")],
                [InlineKeyboardButton("DELETE PICTURE", callback_data="cset_del_start_pic")],
                [InlineKeyboardButton("VIEW PICTURE", callback_data="cset_view_start_pic")],
                [InlineKeyboardButton(f"🖼️ SPOILER - {spoiler_status}", callback_data="cset_tgl_start_spoiler")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_pic":
        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, "set_start_pic")
        await query.answer()
        await edit_or_reply_fn(
            query,
            "<b>SEND ME A PICTURE.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
        )
        async def _spic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if not ans or ans.text == "/cancel" or not ans.photo:
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled or not a photo.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]]) )
            photo_id = ans.photo.file_id
            clear_user_session(user_id)
            save_fn(start_pic=photo_id)
            return await client.send_message(
                chat_id=user_id,
                text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
            )
        asyncio.create_task(_spic_worker())
        return

    if data == "cset_del_start_pic":
        save_fn(start_pic=None)
        await query.answer("Picture deleted!")
        return await edit_or_reply_fn(
            query,
            "❗️ <b>SUCCESSFULLY PICTURE IS DELETED...</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
        )

    if data == "cset_view_start_pic":
        pic = r.get("start_pic")
        if not pic:
            alert_text = f"{client.me.first_name}\n\nYOU DIDN'T ADDED ANY PICTURE..."
            return await query.answer(alert_text, show_alert=True)
        await query.answer()
        spoiler = bool(r.get("start_pic_spoiler", False))
        try:
            return await client.send_photo(
                chat_id=user_id,
                photo=pic,
                caption="🖼️ <b>START PICTURE:</b> ALREADY ADDED PICTURE...",
                has_spoiler=spoiler,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_pic")]])
            )
        except Exception:
            return await query.answer("Could not send photo.", show_alert=True)

    if data == "cset_tgl_start_spoiler":
        spoiler = not bool(r.get("start_pic_spoiler", False))
        save_fn(start_pic_spoiler=spoiler)
        r["start_pic_spoiler"] = spoiler
        return await handle_start_message_callbacks(client, query, "cset_start_pic", user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn)

    # 4. START BUTTON Screen
    if data in ("cset_start_btn", "cset_start_button"):
        s_btns = r.get("start_buttons", [])
        has_btns = bool(s_btns)
        text = (
            "🔘 <b>START BUTTON:</b>\n\n"
            "<b>CREATE CUSTOM URL BUTTONS FOR YOUR START MESSAGE. THE BUTTONS YOU ADD WILL BE SHOWN BELOW START MESSAGE.</b>\n\n"
            "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
            "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
            "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
            "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>"
        )
        if has_btns:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("SEE BUTTON", callback_data="cset_sbtn_see"), InlineKeyboardButton("REMOVE BUTTON", callback_data="cset_sbtn_rem")],
                [InlineKeyboardButton("ADD BUTTON", callback_data="cset_sbtn_add")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        else:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("ADD BUTTON", callback_data="cset_sbtn_add")],
                [InlineKeyboardButton("🪧 BACK", callback_data="cset_start_msg_menu")]
            ])
        return await edit_or_reply_fn(query, text, reply_markup=markup)

    if data == "cset_sbtn_add":
        await query.answer()
        asyncio.create_task(run_start_button_builder(client, user_id, save_fn, cancel_listeners_fn))
        return

    if data == "cset_sbtn_rem":
        save_fn(start_buttons=[])
        await query.answer("Start buttons removed!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY BUTTON DELETED</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="cset_start_btn")]])
        )

    if data == "cset_sbtn_see":
        s_btns = r.get("start_buttons", [])
        rows = []
        for r_item in s_btns:
            row_btns = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row_btns.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            if row_btns:
                rows.append(row_btns)
        rows.append([InlineKeyboardButton("🪧 BACK", callback_data="cset_start_btn")])
        return await edit_or_reply_fn(
            query,
            "🔘 <b>CURRENT CONFIGURED START BUTTONS:</b>",
            reply_markup=InlineKeyboardMarkup(rows)
        )
