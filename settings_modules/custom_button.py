# 🔘 CUSTOM BUTTON SETTINGS MODULE
import asyncio
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def normalize_buttons(raw_btns):
    """Normalize any button format into a flat list of dicts with text and url (up to 7 items)."""
    res = []
    if not raw_btns:
        return res
    if isinstance(raw_btns, list):
        for item in raw_btns:
            if isinstance(item, dict):
                if item.get("text") and item.get("url"):
                    res.append({"text": str(item["text"]).strip()[:64], "url": str(item["url"]).strip()})
                elif "buttons" in item and isinstance(item["buttons"], list):
                    for sub in item["buttons"]:
                        if isinstance(sub, dict) and sub.get("text") and sub.get("url"):
                            res.append({"text": str(sub["text"]).strip()[:64], "url": str(sub["url"]).strip()})
    return res[:7]

def custom_button_markup(has_btns: bool, can_add: bool, back_cb="settings_back", bid=None):
    cb_see = f"m_btn_see:{bid}" if bid else "m_btn_see"
    cb_rem = f"m_btn_rem:{bid}" if bid else "m_btn_rem"
    cb_add = f"m_btn_add:{bid}" if bid else "m_btn_add"
    
    rows = []
    if has_btns:
        rows.append([
            InlineKeyboardButton("SEE BUTTON", callback_data=cb_see),
            InlineKeyboardButton("REMOVE BUTTON", callback_data=cb_rem),
        ])
        if can_add:
            rows.append([InlineKeyboardButton("ADD BUTTON", callback_data=cb_add)])
    else:
        rows.append([InlineKeyboardButton("ADD BUTTON", callback_data=cb_add)])
        
    rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

def render_button_menu_text() -> str:
    return (
        "🔘 <b>MESSAGE BUTTON:</b>\n\n"
        "<b>CREATE CUSTOM URL BUTTONS FOR YOUR STORED MESSAGE. WHEN BOT SEND ANY STORED MESSAGE TO USER THEN BOT ATTACH THE BUTTONS WHICH YOU ADD IN EVERY MESSAGE.</b>\n\n"
        "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
        "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
        "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
        "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>"
    )

async def handle_custom_button_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        last_part = data_str.split(":")[-1]
        if last_part.isdigit() and len(last_part) >= 6:
            target_bid = int(last_part)

    back_cb = f"manage_clone:{target_bid}" if target_bid else "settings_back"
    main_cb = f"custom_button:{target_bid}" if target_bid else "custom_button"
    cb_add = f"m_btn_add:{target_bid}" if target_bid else "m_btn_add"
    cb_rem = f"m_btn_rem:{target_bid}" if target_bid else "m_btn_rem"
    cb_see = f"m_btn_see:{target_bid}" if target_bid else "m_btn_see"

    async def clean_show(txt, markup):
        msg = getattr(query, "message", None) or query
        if msg and (getattr(msg, "photo", None) or getattr(msg, "media", None)):
            try:
                await msg.delete()
            except Exception:
                pass
            return await client.send_message(chat_id=user_id, text=txt, reply_markup=markup)
        return await edit_or_reply_fn(query, txt, reply_markup=markup)

    # 1. Main Button Settings Menu
    if data_str in ("custom_button", "master_custom_button", "cset_button") or data_str.startswith("custom_button:"):
        try:
            await query.answer()
        except Exception:
            pass
        btns = normalize_buttons(r.get("custom_buttons", []))
        has_btns = len(btns) > 0
        can_add = len(btns) < 7
        return await clean_show(render_button_menu_text(), custom_button_markup(has_btns, can_add, back_cb, target_bid))

    # 2. See Configured Buttons
    if data_str in ("m_btn_see", "button_see") or data_str.startswith(("m_btn_see:", "btn_see:")):
        try:
            await query.answer()
        except Exception:
            pass
        btns = normalize_buttons(r.get("custom_buttons", []))
        rows = []
        for b in btns:
            rows.append([InlineKeyboardButton(b["text"], url=b["url"])])
        rows.append([InlineKeyboardButton("‹ BACK", callback_data=main_cb)])
        preview_text = "🔘 <b>YOUR CONFIGURED BUTTONS:</b>" if btns else "🔘 <b>NO BUTTONS CONFIGURED YET.</b>"
        return await clean_show(preview_text, InlineKeyboardMarkup(rows))

    # 3. Remove All Buttons
    if data_str in ("m_btn_rem", "button_remove") or data_str.startswith(("m_btn_rem:", "btn_rem:")):
        save_fn(custom_buttons=[])
        r["custom_buttons"] = []
        try:
            await query.answer("Buttons deleted successfully!")
        except Exception:
            pass
        del_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=main_cb)]])
        return await clean_show("<b>SUCCESSFULLY BUTTON DELETED</b>", del_markup)

    # 4. Add Button (One by one, up to 7 buttons)
    if data_str in ("m_btn_add", "button_add") or data_str.startswith(("m_btn_add:", "btn_add:")):
        btns = normalize_buttons(r.get("custom_buttons", []))
        if len(btns) >= 7:
            try:
                await query.answer("⚠️ You can add a maximum of 7 buttons only!", show_alert=True)
            except Exception:
                pass
            return

        cancel_listeners_fn(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"c_add_btn_{user_id}")
        try:
            await query.answer()
        except Exception:
            pass

        btn_num = len(btns) + 1
        prompt_text = (
            f"🪧 <b>BUTTON {btn_num}</b> ❞\n\n"
            "<b>Send the button text.</b>\n\n"
            "<i>Maximum length: 64 characters</i>\n\n"
            "/cancel - <b>To cancel this process.</b>"
        )
        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=main_cb)]])
        await clean_show(prompt_text, prompt_markup)

        async def _add_btn_worker():
            # Step A: Get Button Text
            btn_text = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    clear_user_session(user_id)
                    cur_b = normalize_buttons(r.get("custom_buttons", []))
                    await clean_show(render_button_menu_text(), custom_button_markup(len(cur_b) > 0, len(cur_b) < 7, back_cb, target_bid))
                    return

                if not is_user_session_active(user_id, sess_token):
                    return
                try:
                    await ans.delete()
                except Exception:
                    pass

                t = (ans.text or ans.caption or "").strip()
                if t == "/cancel":
                    clear_user_session(user_id)
                    cur_b = normalize_buttons(r.get("custom_buttons", []))
                    await clean_show(render_button_menu_text(), custom_button_markup(len(cur_b) > 0, len(cur_b) < 7, back_cb, target_bid))
                    return

                if not t:
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Please send a valid button text:</b>")
                    continue
                if len(t) > 64:
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Button text is too long! Max 64 characters. Please send again:</b>")
                    continue

                btn_text = t
                break

            if not is_user_session_active(user_id, sess_token):
                return

            # Step B: Get Button URL
            url_prompt_text = (
                f"🔗 <b>BUTTON {btn_num}</b> ❞\n\n"
                "<b>Send the button URL.</b>\n\n"
                "<b>Examples:</b>\n"
                "<code>https://t.me/your_channel</code>\n"
                "<code>https://google.com</code>\n\n"
                "/cancel - <b>To cancel this process.</b>"
            )
            await clean_show(url_prompt_text, prompt_markup)

            btn_url = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    clear_user_session(user_id)
                    cur_b = normalize_buttons(r.get("custom_buttons", []))
                    await clean_show(render_button_menu_text(), custom_button_markup(len(cur_b) > 0, len(cur_b) < 7, back_cb, target_bid))
                    return

                if not is_user_session_active(user_id, sess_token):
                    return
                try:
                    await ans.delete()
                except Exception:
                    pass

                u = (ans.text or ans.caption or "").strip()
                if u == "/cancel":
                    clear_user_session(user_id)
                    cur_b = normalize_buttons(r.get("custom_buttons", []))
                    await clean_show(render_button_menu_text(), custom_button_markup(len(cur_b) > 0, len(cur_b) < 7, back_cb, target_bid))
                    return

                if not (u.startswith("http://") or u.startswith("https://") or u.startswith("tg://")):
                    await client.send_message(chat_id=user_id, text="⚠️ <b>Invalid URL! It must start with http:// or https://. Please send again:</b>")
                    continue

                btn_url = u
                break

            if not is_user_session_active(user_id, sess_token):
                return

            # Step C: Save new button to list
            current_btns = normalize_buttons(r.get("custom_buttons", []))
            current_btns.append({"text": btn_text, "url": btn_url})
            current_btns = current_btns[:7]

            save_fn(custom_buttons=current_btns)
            r["custom_buttons"] = current_btns
            clear_user_session(user_id)

            success_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=main_cb)]])
            await clean_show("<b>SUCCESSFULLY BUTTON ADDED ✅</b>", success_markup)

        asyncio.create_task(_add_btn_worker())
        return
