# 🔘 CUSTOM BUTTON SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

async def run_button_builder(client, user_id, b_type: str, back_callback: str, save_fn, cancel_listeners_fn):
    cancel_listeners_fn(client, user_id, user_id)
    sess_token = start_user_session(user_id, f"c_build_btn_{b_type}")
    rows = []
    row_idx = 1
    
    while is_user_session_active(user_id, sess_token):
        count_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("1️⃣ One Button"), KeyboardButton("2️⃣ Two Buttons")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        msg_text = (
            f"🎯 <b>ROW {row_idx}</b>\n\n"
            "<b>How many buttons do you want in this row?</b>\n\n"
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
            if "1" in txt:
                btn_count = 1
                break
            elif "2" in txt:
                btn_count = 2
                break
            else:
                await client.send_message(chat_id=user_id, text="⚠️ <b>Please choose 1 or 2 buttons using the keyboard below.</b>", reply_markup=count_kb)
        
        if not is_user_session_active(user_id, sess_token):
            return
        
        row_buttons = []
        for b_i in range(1, btn_count + 1):
            lbl = f"Button {b_i}" if btn_count > 1 else "Button"
            
            # Step A: Button Text
            await client.send_message(
                chat_id=user_id,
                text=f"📝 <b>ROW {row_idx} - {lbl.upper()} TEXT:</b>\n\n<b>Send the text for this button (Max 64 characters):</b>",
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
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Please send a valid text message.</b>")
                    continue
                if len(t) > 64:
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Button text is too long. Please keep it under 64 characters:</b>")
                    continue
                b_text = t
                break
            
            if not is_user_session_active(user_id, sess_token):
                return
            
            # Step B: Button URL
            await client.send_message(
                chat_id=user_id,
                text=f"🔗 <b>ROW {row_idx} - {lbl.upper()} URL:</b>\n\n<b>Send the URL for this button (Must start with http:// or https://):</b>"
            )
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
                if not (u.startswith("http://") or u.startswith("https://")):
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Invalid URL! It must start with http:// or https://. Please send again:</b>")
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
                text=f"🎨 <b>ROW {row_idx} - {lbl.upper()} STYLE:</b>\n\n<b>Select the button style / color using the keyboard below:</b>",
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
        
        # Step D: Next row or finish
        next_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("➕ Add Another Row"), KeyboardButton("✅ Finish & Save Buttons")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await client.send_message(
            chat_id=user_id,
            text=f"✅ <b>ROW {row_idx} ADDED!</b>\n\n<b>Do you want to add another row of buttons or finish?</b>",
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
            if "finish" in nxt or "save" in nxt or "✅" in nxt:
                finish = True
                break
            elif "add" in nxt or "another" in nxt or "➕" in nxt:
                row_idx += 1
                break
            else:
                await client.send_message(chat_id=user_id, text="⚠️ <b>Please choose an option below.</b>", reply_markup=next_kb)
        
        if finish:
            break

    clear_user_session(user_id)
    save_fn(custom_buttons=rows)
    
    preview_rows = []
    for r_item in rows:
        r_btns = []
        for b in r_item.get("buttons", []):
            r_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
        if r_btns:
            preview_rows.append(r_btns)
    preview_rows.append([InlineKeyboardButton("🪧 BACK TO SETTINGS", callback_data=back_callback)])
    
    await client.send_message(
        chat_id=user_id,
        text="🎉 <b>CUSTOM BUTTONS SAVED SUCCESSFULLY!</b>\n\n<b>Preview of your buttons:</b>",
        reply_markup=InlineKeyboardMarkup(preview_rows)
    )

async def handle_custom_button_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn):
    if data in ("custom_button", "master_custom_button", "cset_button"):
        btns = r.get("custom_buttons", [])
        has_btns = bool(btns)
        text = (
            "🔘 <b>MESSAGE BUTTON:</b>\n\n"
            "<b>CREATE CUSTOM URL BUTTONS FOR YOUR STORED MESSAGE. THE BUTTONS YOU ADD WILL BE SHOWN BELOW EVERY MESSAGE.</b>\n\n"
            "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
            "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
            "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
            "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>"
        )
        first_btn = InlineKeyboardButton("SEE BUTTON", callback_data="m_btn_see") if has_btns else InlineKeyboardButton("ADD BUTTON", callback_data="m_btn_add")
        rows = [
            [first_btn, InlineKeyboardButton("REMOVE BUTTON", callback_data="m_btn_rem")],
        ]
        if has_btns:
            rows.insert(1, [InlineKeyboardButton("ADD BUTTON", callback_data="m_btn_add")])
        rows.append([InlineKeyboardButton("🪧 BACK", callback_data="settings")])
        return await edit_or_reply_fn(query, text, reply_markup=InlineKeyboardMarkup(rows))

    if data in ("m_btn_add", "button_add"):
        await query.answer()
        asyncio.create_task(run_button_builder(client, user_id, "custom", "custom_button", save_fn, cancel_listeners_fn))
        return

    if data in ("m_btn_rem", "button_remove"):
        save_fn(custom_buttons=[])
        await query.answer("Buttons removed successfully!")
        return await edit_or_reply_fn(
            query,
            "<b>SUCCESSFULLY REMOVED BUTTONS ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪧 BACK", callback_data="custom_button")]])
        )

    if data in ("m_btn_see", "button_see"):
        btns = r.get("custom_buttons", [])
        rows = []
        for r_item in btns:
            row_btns = []
            if isinstance(r_item, dict) and "buttons" in r_item:
                for b in r_item["buttons"]:
                    row_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
            elif isinstance(r_item, dict) and "text" in r_item:
                row_btns.append(InlineKeyboardButton(r_item["text"], url=r_item.get("url", "https://t.me")))
            if row_btns:
                rows.append(row_btns)
        rows.append([InlineKeyboardButton("🪧 BACK", callback_data="custom_button")])
        return await edit_or_reply_fn(
            query,
            "🔘 <b>CURRENT CONFIGURED BUTTONS:</b>",
            reply_markup=InlineKeyboardMarkup(rows)
        )
