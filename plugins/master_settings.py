# ASH FILE STORE - MASTER BOT SETTINGS UI
import asyncio
import time
import re
import os
import datetime
from pyrogram import filters, Client
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session, cancel_all_listeners
from clone_plugins.users_api import (
    get_user, update_user_info, get_short_link, validate_shortener_token,
    parse_time_string, format_time_minutes, is_user_premium,
    parse_auto_delete_time, format_auto_delete_time
)
from settings_modules.force_sub import handle_fsub_callbacks
from config import ADMINS, BOT_USERNAME

_START_TIME = time.time()

def db():
    from plugins.clone import mongo_db
    return mongo_db

def master_record():
    m = db()
    if m is None:
        return {}
    return m.master_settings.find_one({"type": "master_config"}) or {}

def save_master(**data):
    m = db()
    if m is not None:
        m.master_settings.update_one({"type": "master_config"}, {"$set": data}, upsert=True)

def is_admin(uid):
    try:
        return int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]
    except Exception:
        return False

def docs_for(uid):
    m = db()
    if m is None:
        return []
    q = {} if is_admin(uid) else {"user_id": int(uid)}
    return list(m.bots.find(q, {"token": 0}).sort("bot_id", 1))

def cancel_user_listeners(client, chat_id, user_id=None):
    cancel_all_listeners(client, chat_id, user_id)

async def edit_or_reply(query_or_msg, text, reply_markup=None, disable_web_page_preview=False):
    msg = getattr(query_or_msg, "message", None) or query_or_msg
    if not msg:
        return
    try:
        if getattr(msg, "photo", None) or getattr(msg, "media", None):
            try:
                return await msg.edit_caption(caption=text, reply_markup=reply_markup)
            except Exception as e:
                err = str(e).upper()
                if "MESSAGE_NOT_MODIFIED" in err:
                    return msg
                try:
                    return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
                except Exception:
                    pass
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
        else:
            try:
                return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
            except Exception as e:
                err = str(e).upper()
                if "MESSAGE_NOT_MODIFIED" in err:
                    return msg
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except Exception:
        pass

# ----------------- MARKUPS & MENUS ----------------- #

def master_settings_markup(back_cb="settings_back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 PREMIUM PLAN", callback_data="master_premium_plan")],
        [InlineKeyboardButton("🆓 FREE USAGE LIMIT", callback_data="master_free_limit_menu")],
        [InlineKeyboardButton("🌍 REFER AND EARN", callback_data="master_refer_earn")],
        [InlineKeyboardButton("🖇️ LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("🎯 TOKEN VERIFICATION", callback_data="master_token_main")],
        [InlineKeyboardButton("🔒 FORCE SUBSCRIBE", callback_data="master_fsub_menu")],
        [InlineKeyboardButton("🍿 CAPTION", callback_data="custom_caption"), InlineKeyboardButton("🖼️ THUMBNAIL", callback_data="custom_thumbnail")],
        [InlineKeyboardButton("🔘 BUTTON", callback_data="custom_button"), InlineKeyboardButton("♻️ AUTO DELETE", callback_data="master_auto_delete_menu")],
        [InlineKeyboardButton("♾️ PERMANENT LINK", callback_data="master_permanent_link")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("🔙 BACK", callback_data=back_cb)]
    ])

def manage_clones_markup(uid, back_cb="settings_back"):
    from clone_plugins import master_manager
    return master_manager.manage_clones_markup(uid, back_cb=back_cb)

def master_token_verification_main_markup(r=None):
    from settings_modules.token_verify import token_verification_main_markup
    return token_verification_main_markup(r, prefix_cb="master")

def master_single_token_verification_markup(slot: int, is_on: bool):
    from settings_modules.token_verify import single_token_verification_markup
    return single_token_verification_markup(slot, is_on, prefix_cb="master")

# ----------------- BUTTON BUILDER WIZARD ----------------- #

async def run_master_button_builder(client, user_id, b_type: str, back_callback: str):
    cancel_user_listeners(client, user_id, user_id)
    sess_token = start_user_session(user_id, f"m_build_btn_{b_type}")
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
    save_master(custom_buttons=rows)
    
    preview_rows = []
    for r_item in rows:
        r_btns = []
        for b in r_item.get("buttons", []):
            r_btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
        if r_btns:
            preview_rows.append(r_btns)
    preview_rows.append([InlineKeyboardButton("‹ BACK TO SETTINGS", callback_data=back_callback)])
    
    await client.send_message(
        chat_id=user_id,
        text="🎉 <b>CUSTOM BUTTONS SAVED SUCCESSFULLY!</b>\n\n<b>Preview of your buttons:</b>",
        reply_markup=InlineKeyboardMarkup(preview_rows)
    )

# ----------------- ENTRY POINTS ----------------- #

async def send_settings_menu(client, message_or_user_id):
    uid = getattr(message_or_user_id, "from_user", None) and message_or_user_id.from_user.id or (
        isinstance(message_or_user_id, int) and message_or_user_id or getattr(message_or_user_id, "chat", None) and message_or_user_id.chat.id
    )
    cancel_user_listeners(client, uid, uid)
    r = master_record()
    p_days = r.get("plan_days", 3)
    p_clones = r.get("plan_clones", 40)
    text = (
        f"🌟 <b>AVAILABLE PLANS • {p_days:02d} DAYS - {p_clones} ...</b>\n\n"
        "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
    )
    if hasattr(message_or_user_id, "reply"):
        return await message_or_user_id.reply(text, reply_markup=master_settings_markup())
    return await client.send_message(uid, text, reply_markup=master_settings_markup())

async def send_clone_settings_menu(client, message_or_user_id, bid=None):
    from clone_plugins import master_manager
    uid = getattr(message_or_user_id, "from_user", None) and message_or_user_id.from_user.id or (
        isinstance(message_or_user_id, int) and message_or_user_id or getattr(message_or_user_id, "chat", None) and message_or_user_id.chat.id
    )
    cancel_user_listeners(client, uid, uid)
    m = db()
    bot_doc = None
    if m is not None and bid:
        try:
            bot_doc = m.bots.find_one({"bot_id": int(bid)})
        except Exception:
            bot_doc = None
    if not bot_doc and m is not None:
        docs = list(m.bots.find({"user_id": int(uid)}))
        if docs:
            bot_doc = docs[0]
            bid = bot_doc.get("bot_id")
    
    if not bot_doc:
        return await send_manage_clones(client, message_or_user_id)

    # Store active editing clone in active_clone_edit
    if m is not None and bid:
        m.active_clone_edit.update_one({"user_id": int(uid)}, {"$set": {"bot_id": int(bid)}}, upsert=True)

    bot_name = bot_doc.get("username") or bot_doc.get("name") or "Your Clone"
    r = master_record()
    p_days = r.get("plan_days", 3)
    p_clones = r.get("plan_clones", 40)
    text = (
        f"🌟 <b>AVAILABLE PLANS • {p_days:02d} DAYS - {p_clones} ...</b>\n\n"
        "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
    )
    msg_target = getattr(message_or_user_id, "message", None) or (message_or_user_id if hasattr(message_or_user_id, "reply") else None)
    if msg_target:
        return await edit_or_reply(msg_target, text, reply_markup=master_manager.manage_markup(bid, back_cb="my_clones"))
    return await client.send_message(uid, text, reply_markup=master_manager.manage_markup(bid, back_cb="my_clones"))

async def send_manage_clones(client, message_or_user_id, message=None):
    from clone_plugins import master_manager
    uid = getattr(message_or_user_id, "from_user", None) and message_or_user_id.from_user.id or (
        isinstance(message_or_user_id, int) and message_or_user_id or getattr(message_or_user_id, "chat", None) and message_or_user_id.chat.id
    )
    msg_target = message or (message_or_user_id if hasattr(message_or_user_id, "reply") else None)
    text = (
        "👑 <b>CLONE MENU</b>\n\n"
        "<i>\" WELCOME TO YOUR CLONE BOT MANAGEMENT HUB! CUSTOMIZE YOUR BOT SETTINGS OR MANAGE ITS STATUS USING THE OPTIONS BELOW. \"</i>\n\n"
        "⚙️ <b>QUICK COMMANDS</b>\n\n"
        "🚀 /activate - ACTIVATE YOUR CLONE BOT\n"
        "🗑️ /delete - PERMANENTLY DELETE YOUR CLONE BOT\n\n"
        "🎨 <b>BOT CUSTOMIZATION</b>\n\n"
        "✨ <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
    )
    if msg_target:
        return await edit_or_reply(msg_target, text, reply_markup=master_manager.manage_clones_markup(uid, back_cb="settings_back", is_clone=False))
    return await client.send_message(uid, text, reply_markup=master_manager.manage_clones_markup(uid, back_cb="settings_back", is_clone=False))

# ----------------- CALLBACK QUERY ROUTER ----------------- #

async def callbacks(client, query):
    user_id = query.from_user.id
    data = query.data or ""
    
    # Check if target bid is in callback data (e.g. cset_prem:123456)
    target_bid = None
    if ":" in data:
        last_part = data.split(":")[-1]
        if last_part.isdigit() and len(last_part) >= 6:
            target_bid = int(last_part)
            
    m = db()
    if not target_bid and m is not None:
        active_rec = m.active_clone_edit.find_one({"user_id": int(user_id)})
        if active_rec:
            target_bid = active_rec.get("bot_id")

    if target_bid and m is not None:
        target_doc = m.bots.find_one({"bot_id": int(target_bid)})
        if target_doc:
            r = target_doc
        else:
            r = master_record()
    else:
        r = master_record()

    def save_master(**kwargs):
        m_inner = db()
        if m_inner is not None:
            if target_bid:
                m_inner.bots.update_one({"bot_id": int(target_bid)}, {"$set": kwargs}, upsert=True)
            else:
                m_inner.master_settings.update_one({}, {"$set": kwargs}, upsert=True)

    me = await client.get_me()

    if data in ("settings", "settings_back", "master_settings"):
        cancel_user_listeners(client, user_id, user_id)
        if target_bid and m is not None:
            target_doc = m.bots.find_one({"bot_id": int(target_bid)})
            if target_doc:
                from clone_plugins import master_manager
                text = (
                    "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
                )
                return await edit_or_reply(query, text, reply_markup=master_manager.manage_markup(target_bid, back_cb="my_clones"))
        p_days = r.get("plan_days", 3)
        p_clones = r.get("plan_clones", 40)
        text = (
            f"🌟 <b>AVAILABLE PLANS • {p_days:02d} DAYS - {p_clones} ...</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=master_settings_markup())

    if data in ("my_clone", "my_clones", "clone_my_bots"):
        from clone_plugins import master_manager
        # Clear active clone edit when user returns to clone menu
        if m is not None:
            m.active_clone_edit.delete_one({"user_id": int(user_id)})
        text = (
            "👑 <b>CLONE MENU</b>\n\n"
            "<i>\" WELCOME TO YOUR CLONE BOT MANAGEMENT HUB! CUSTOMIZE YOUR BOT SETTINGS OR MANAGE ITS STATUS USING THE OPTIONS BELOW. \"</i>\n\n"
            "⚙️ <b>QUICK COMMANDS</b>\n\n"
            "🚀 /activate - ACTIVATE YOUR CLONE BOT\n"
            "🗑️ /delete - PERMANENTLY DELETE YOUR CLONE BOT\n\n"
            "🎨 <b>BOT CUSTOMIZATION</b>\n\n"
            "✨ <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
        )
        return await edit_or_reply(query, text, reply_markup=master_manager.manage_clones_markup(user_id, back_cb="settings_back", is_clone=False))

    if data in ("create_clone_prompt", "clone_limit") or data.startswith(("manage_clone:", "cm:", "cad:", "cmdelete:")):
        from clone_plugins import master_manager
        return await master_manager.handle_clone_callbacks(client, query)

    # --- TOKEN VERIFICATION --- #
    if data in ("master_token_main", "master_token_verification"):
        text = (
            "⏰ <b>TOKEN VERIFICATION:</b>\n\n"
            "<b>TOKEN VERIFICATION: A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=master_token_verification_main_markup())

    if data.startswith("master_token_verification:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False))
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        return await edit_or_reply(query, text, reply_markup=master_single_token_verification_markup(slot, is_on))

    if data.startswith("m_v_toggle:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        new_state = not bool(v_cfg.get("is_on", False))
        v_cfg["is_on"] = new_state
        save_master(**{v_key: v_cfg})
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        await query.answer(f"Verification {'Enabled' if new_state else 'Disabled'}!")
        return await edit_or_reply(query, text, reply_markup=master_single_token_verification_markup(slot, new_state))

    if data.startswith("m_v_stats:"):
        slot = int(data.split(":")[1])
        today_count = r.get(f"verified_today_{slot}", 0)
        bot_title = me.first_name or me.username or "ASH BOT"
        return await query.answer(f"{bot_title}\n\nTotal Verified Today - {today_count}", show_alert=True)

    if data.startswith("m_v_shortner:"):
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
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET SHORTNER", callback_data=f"m_set_v_shortner:{slot}")],
            [InlineKeyboardButton("DELETE SHORTNER", callback_data=f"m_del_v_shortner:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_shortner:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg.pop("shortner_site", None)
        v_cfg.pop("shortner_api", None)
        save_master(**{v_key: v_cfg})
        await query.answer("Shortener deleted!")
        return await callbacks(client, type("Q", (), {"data": f"m_v_shortner:{slot}", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data.startswith("m_set_v_shortner:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, f"m_v_shortner_{slot}")
        await query.answer()
        
        prompt_msg = await query.message.reply(
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
            curr_r = master_record()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["shortner_site"] = site
            v_cfg["shortner_api"] = api_key
            save_master(**{v_key: v_cfg})
            clear_user_session(user_id)
            
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} SHORTNER CONFIGURED SUCCESSFULLY!</b>\n\n"
                f"🌐 <b>Site:</b> <code>{site}</code>\n"
                f"🔑 <b>API:</b> <code>{api_key}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_shortner_worker())
        return

    if data.startswith("m_v_tutorial:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        tut = v_cfg.get("tutorial") or "Not Set"
        text = (
            f"🍿 <b>{prefix} VERIFY TUTORIAL:</b>\n\n"
            f"📹 <b>VIDEO / LINK:</b> <code>{tut}</code>"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET TUTORIAL", callback_data=f"m_set_v_tut:{slot}")],
            [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"m_del_v_tut:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_tut:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg.pop("tutorial", None)
        save_master(**{v_key: v_cfg})
        await query.answer("Tutorial deleted!")
        return await callbacks(client, type("Q", (), {"data": f"m_v_tutorial:{slot}", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data.startswith("m_set_v_tut:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_user_listeners(client, user_id, user_id)
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
            curr_r = master_record()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["tutorial"] = t_url
            save_master(**{v_key: v_cfg})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} TUTORIAL SAVED!</b>\n\n<code>{t_url}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_tut_worker())
        return

    if data.startswith("m_v_time:"):
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
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET VERIFY TIME", callback_data=f"m_set_v_time:{slot}")],
            [InlineKeyboardButton("RESET TIME", callback_data=f"m_del_v_time:{slot}")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]
        ]))

    if data.startswith("m_del_v_time:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["time"] = 1440
        save_master(**{v_key: v_cfg})
        await query.answer("Time reset to 24 Hours!")
        return await callbacks(client, type("Q", (), {"data": f"m_v_time:{slot}", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data.startswith("m_set_v_time:"):
        slot = int(data.split(":")[1])
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        cancel_user_listeners(client, user_id, user_id)
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
            curr_r = master_record()
            v_cfg = curr_r.get(v_key, {})
            v_cfg["time"] = mins
            save_master(**{v_key: v_cfg})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>{prefix} VERIFY TIME UPDATED!</b>\n\n⏳ <b>New Duration:</b> <code>{format_time_minutes(mins)}</code> ({mins} mins)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"master_token_verification:{slot}")]])
            )
        asyncio.create_task(_time_worker())
        return

    # Verify Log Channel
    if data == "master_verify_log_channel":
        log_ch = r.get("verify_log_channel") or "Not Set"
        text = (
            "📢 <b>VERIFY LOG CHANNEL:</b>\n\n"
            f"🆔 <b>CURRENT LOG CHANNEL:</b> <code>{log_ch}</code>\n\n"
            "<b>All verification activities and token logs will be forwarded to this channel.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET LOG CHANNEL", callback_data="m_set_v_log")],
            [InlineKeyboardButton("DELETE LOG CHANNEL", callback_data="m_del_v_log")],
            [InlineKeyboardButton("‹ BACK", callback_data="master_token_main")]
        ]))

    if data == "m_del_v_log":
        save_master(verify_log_channel=None)
        await query.answer("Verify log channel deleted!")
        return await callbacks(client, type("Q", (), {"data": "master_verify_log_channel", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_v_log":
        cancel_user_listeners(client, user_id, user_id)
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
            save_master(verify_log_channel=ch_id)
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>VERIFY LOG CHANNEL CONNECTED!</b>\n\n🆔 <b>Channel ID:</b> <code>{ch_id}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_token_main")]])
            )
        asyncio.create_task(_log_worker())
        return

    # --- BUTTONS --- #
    if data in ("custom_button", "master_custom_button"):
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
        rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings")])
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(rows))

    if data == "m_btn_add":
        await query.answer()
        asyncio.create_task(run_master_button_builder(client, user_id, "custom", "custom_button"))
        return

    if data == "m_btn_rem":
        save_master(custom_buttons=[])
        await query.answer("Buttons removed successfully!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY REMOVED BUTTONS ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_button")]])
        )

    if data == "m_btn_see":
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
        rows.append([InlineKeyboardButton("‹ BACK", callback_data="custom_button")])
        return await edit_or_reply(
            query,
            "<b>HERE ARE YOUR CONFIGURED BUTTONS:</b>",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    # --- FREE USAGE LIMIT --- #
    if data == "master_free_limit_menu":
        f_limit = r.get("free_limit", {})
        count = f_limit.get("count", 0)
        num = f_limit.get("num", 0)
        unit = f_limit.get("unit", "day")
        is_on = bool(f_limit.get("enabled", False))
        if is_on and count > 0:
            status_desc = f"📊 <b>CURRENT FREE USAGE LIMIT:</b>\n* <b>FILES ALLOWED:</b> {count} FILES\n* <b>RESET PERIOD:</b> EVERY {num} {unit.upper()}(S)"
        else:
            status_desc = "⚠️ <b>FREE USAGE LIMIT:</b> 🚫 <b>DISABLED\n(UNLIMITED ACCESS)</b>"
            
        text = (
            "🎟️ <b>FREE USAGE LIMIT:</b>\n\n"
            "<b>FREE USAGE LIMIT ALLOWS YOU TO CONTROL HOW MANY FILES A USER CAN ACCESS FOR FREE THROUGH YOUR SHARE LINK. YOU CAN SET ANY CUSTOM LIMIT (E.G., DAYS, WEEKS, MONTHS, OR YEARS).</b>\n\n"
            "⚠️ <b>NOTE:</b>\n"
            "1. <b>IF NO LIMIT IS SET, THE FREE LIMIT FEATURE IS COMPLETELY DISABLED, AND USERS CAN ACCESS UNLIMITED FILES WITHOUT ANY RESTRICTIONS.</b>\n"
            "2. <b>THIS FREE LIMIT FEATURE WILL ONLY WORK WHEN PREMIUM FEATURE OR TOKEN VERIFICATION FEATURE IS ENABLED.</b>\n\n"
            "💡 <b>EXAMPLE:</b>\n"
            "<b>IF YOU SET A LIMIT OF 5 FILES EVERY 1 MONTH, THEN A USER OPENING YOUR LINK CAN ONLY GET 5 FILES FOR FREE IN THAT MONTH. ONCE THE LIMIT IS REACHED, THEY MUST WAIT UNTIL THE MONTH RESETS TO GET MORE.</b>\n\n"
            f"{status_desc}"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET FREE USAGE LIMIT", callback_data="m_set_free_limit")],
                [InlineKeyboardButton("DELETE FREE USAGE LIMIT", callback_data="m_del_free_limit")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "m_del_free_limit":
        save_master(free_limit={"enabled": False, "count": 0, "num": 0, "unit": "day"})
        await query.answer("Free limit deleted!")
        return await callbacks(client, type("Q", (), {"data": "master_free_limit_menu", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_free_limit":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_free_limit")
        await query.answer()
        await query.message.reply(
            "🎟️ <b>SET FREE USAGE LIMIT:</b>\n\n"
            "<b>Step 1/2: How many files can a free user access? (Send a number, e.g. <code>5</code>):</b>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        async def _limit_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            if not txt.isdigit() or int(txt) <= 0:
                await client.send_message(user_id, "❌ <b>Invalid number. Must be a positive integer.</b>")
                clear_user_session(user_id)
                return
            count = int(txt)
            
            unit_kb = ReplyKeyboardMarkup([
                [KeyboardButton("1 Day"), KeyboardButton("7 Days")],
                [KeyboardButton("1 Month"), KeyboardButton("1 Year")]
            ], resize_keyboard=True, one_time_keyboard=True)
            
            await client.send_message(
                user_id,
                f"🎟️ <b>Step 2/2: Choose reset interval for {count} files:</b>",
                reply_markup=unit_kb
            )
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt2 = (ans2.text or "").strip().lower()
            if txt2 == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                clear_user_session(user_id)
                return
            
            num = 1
            unit = "day"
            if "month" in txt2:
                unit = "month"
                num = 1
            elif "year" in txt2:
                unit = "year"
                num = 1
            elif "7" in txt2 or "week" in txt2:
                unit = "day"
                num = 7
            else:
                unit = "day"
                num = 1
                
            save_master(free_limit={"enabled": True, "count": count, "num": num, "unit": unit})
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>FREE USAGE LIMIT SET TO {count} FILES EVERY {num} {unit.upper()}(S)!</b>",
                reply_markup=ReplyKeyboardRemove()
            )
            await client.send_message(
                user_id,
                "<b>Settings Updated ✅</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO SETTINGS", callback_data="settings")]])
            )
        asyncio.create_task(_limit_worker())
        return

    # --- PREMIUM PLAN --- #
    if data == "master_premium_plan":
        prem_enabled = bool(r.get("premium_enabled", False))
        status_txt = "ON ✅" if prem_enabled else "OFF ❌"
        p_text = r.get("premium_plan_text") or "Default plans: 1 Month - ₹50 | 1 Year - ₹300"
        p_upi = r.get("premium_upi_id") or "Not Set"
        text = (
            "💳 <b>PREMIUM PLAN SETTINGS:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n"
            f"• <b>UPI ID:</b> <code>{p_upi}</code>\n"
            f"• <b>PLAN DESCRIPTION:</b>\n{p_text}\n\n"
            "<b>Use options below to customize your premium offerings.</b>"
        )
        tgl_label = "DISABLE PREMIUM" if prem_enabled else "ENABLE PREMIUM"
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_label, callback_data="m_prem_tgl")],
            [InlineKeyboardButton("SET PLAN TEXT", callback_data="m_set_prem_txt"), InlineKeyboardButton("SET UPI ID", callback_data="m_set_prem_upi")],
            [InlineKeyboardButton("SET PAYMENT QR/PHOTO", callback_data="m_set_prem_pic")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_prem_tgl":
        new_s = not bool(r.get("premium_enabled", False))
        save_master(premium_enabled=new_s)
        await query.answer(f"Premium plan {'Enabled' if new_s else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "master_premium_plan", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_prem_txt":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_txt")
        await query.answer()
        await query.message.reply("💳 <b>Send new Premium Plan description text:</b>\n\n<i>Send /cancel to abort.</i>")
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
            save_master(premium_plan_text=t)
            clear_user_session(user_id)
            await client.send_message(user_id, "✅ <b>Premium plan text updated!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
        asyncio.create_task(_ptxt_worker())
        return

    if data == "m_set_prem_upi":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_upi")
        await query.answer()
        await query.message.reply("💳 <b>Send your UPI ID (e.g. <code>example@okaxis</code>):</b>\n\n<i>Send /cancel to abort.</i>")
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
            save_master(premium_upi_id=u)
            clear_user_session(user_id)
            await client.send_message(user_id, f"✅ <b>UPI ID set to:</b> <code>{u}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
        asyncio.create_task(_pupi_worker())
        return

    if data == "m_set_prem_pic":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_prem_pic")
        await query.answer()
        await query.message.reply("💳 <b>Send a photo for Payment QR / Banner:</b>\n\n<i>Send /cancel to abort.</i>")
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
                save_master(premium_plan_photo=pic_id)
                clear_user_session(user_id)
                await client.send_message(user_id, "✅ <b>Payment QR / Photo saved!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_premium_plan")]]))
            else:
                await client.send_message(user_id, "❌ <b>Please send a valid photo!</b>")
                clear_user_session(user_id)
        asyncio.create_task(_ppic_worker())
        return

    # --- REFER AND EARN --- #
    if data == "master_refer_earn":
        ref_on = bool(r.get("refer_enabled", False))
        pts = r.get("refer_points", 10)
        target = r.get("refer_target", 50)
        status_txt = "ON ✅" if ref_on else "OFF ❌"
        text = (
            "🌍 <b>REFER AND EARN:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n"
            f"• <b>POINTS PER REFERRAL:</b> <code>{pts}</code>\n"
            f"• <b>POINTS TO UNLOCK REWARD:</b> <code>{target}</code>\n\n"
            "<b>Reward users for inviting their friends to the bot!</b>"
        )
        tgl_btn = "DISABLE REFER & EARN" if ref_on else "ENABLE REFER & EARN"
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_refer")],
            [InlineKeyboardButton("SET POINTS PER REFER", callback_data="m_set_refer_pts")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_tgl_refer":
        new_s = not bool(r.get("refer_enabled", False))
        save_master(refer_enabled=new_s)
        await query.answer(f"Refer & Earn {'Enabled' if new_s else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "master_refer_earn", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_refer_pts":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_refer_pts")
        await query.answer()
        await query.message.reply("🌍 <b>Send points to award per referral (e.g. <code>10</code>):</b>\n\n<i>Send /cancel to abort.</i>")
        async def _ref_worker():
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
            if not t.isdigit():
                await client.send_message(user_id, "❌ <b>Must be a number.</b>")
                clear_user_session(user_id)
                return
            save_master(refer_points=int(t))
            clear_user_session(user_id)
            await client.send_message(user_id, f"✅ <b>Points set to:</b> {t}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_refer_earn")]]))
        asyncio.create_task(_ref_worker())
        return

    # --- MAIN LINK SHORTENER --- #
    if data in ("link_shortener", "cset_shortener"):
        site = r.get("shortener_site") or "Not Set"
        api = r.get("shortener_api") or "Not Set"
        text = (
            "🔗 <b>MAIN LINK SHORTNER:</b>\n\n"
            f"🌐 <b>DOMAIN / SITE:</b> <code>{site}</code>\n"
            f"🔑 <b>API KEY:</b> <code>{api}</code>\n\n"
            "<b>Connect your URL shortener service to earn from link generations.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET SHORTNER", callback_data="m_set_main_shortener")],
            [InlineKeyboardButton("DELETE SHORTNER", callback_data="m_del_main_shortener")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_del_main_shortener":
        save_master(shortener_site=None, shortener_api=None)
        await query.answer("Shortener removed!")
        return await callbacks(client, type("Q", (), {"data": "link_shortener", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_main_shortener":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_main_short")
        await query.answer()
        await query.message.reply("🔗 <b>Send your shortener website (e.g. <code>shareus.io</code>):</b>\n\n<i>Send /cancel to abort.</i>")
        async def _m_short_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            st = (ans.text or "").strip()
            if st == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            st = st.replace("http://", "").replace("https://", "").strip("/")
            await client.send_message(user_id, f"🔑 <b>Send your API key for <code>{st}</code>:</b>")
            try:
                ans2 = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            ap = (ans2.text or "").strip()
            if ap == "/cancel":
                await client.send_message(user_id, "❌ <b>Cancelled.</b>")
                clear_user_session(user_id)
                return
            save_master(shortener_site=st, shortener_api=ap)
            clear_user_session(user_id)
            await client.send_message(
                user_id,
                f"✅ <b>SHORTNER SAVED!</b>\n\n🌐 <b>Site:</b> <code>{st}</code>\n🔑 <b>API:</b> <code>{ap}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="link_shortener")]])
            )
        asyncio.create_task(_m_short_worker())
        return

    # --- FORCE SUBSCRIBE --- #
    if data in ("master_fsub_menu", "m_tgl_fsub", "m_clear_fsub", "m_add_fsub") or data.startswith("cset_fsub"):
        try:
            return await handle_fsub_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply)
        except Exception as e:
            try:
                await query.answer(f"Error: {e}", show_alert=True)
            except Exception:
                pass
            return

    # --- CAPTION --- #
    if data == "custom_caption":
        cap = r.get("custom_caption") or "Default Caption"
        text = (
            "🍿 <b>CUSTOM CAPTION:</b>\n\n"
            f"<b>CURRENT CAPTION:</b>\n<code>{cap}</code>\n\n"
            "<b>Variables available:</b>\n"
            "• <code>{filename}</code> - File Name\n"
            "• <code>{size}</code> - File Size"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET CUSTOM CAPTION", callback_data="m_set_caption")],
            [InlineKeyboardButton("RESET TO DEFAULT", callback_data="m_del_caption")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_del_caption":
        save_master(custom_caption=None)
        await query.answer("Caption reset to default!")
        return await callbacks(client, type("Q", (), {"data": "custom_caption", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_caption":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_caption")
        await query.answer()
        await query.message.reply("🍿 <b>Send your new Custom Caption:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _cap_worker():
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
            save_master(custom_caption=t)
            clear_user_session(user_id)
            await client.send_message(user_id, "✅ <b>Custom Caption updated!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_caption")]]))
        asyncio.create_task(_cap_worker())
        return

    # --- THUMBNAIL --- #
    if data == "custom_thumbnail":
        thumb = r.get("custom_thumbnail")
        status_txt = "Configured ✅" if thumb else "Not Set ❌"
        text = f"🖼️ <b>CUSTOM THUMBNAIL:</b>\n\n<b>Status:</b> {status_txt}"
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SET THUMBNAIL", callback_data="m_set_thumb")],
            [InlineKeyboardButton("DELETE THUMBNAIL", callback_data="m_del_thumb")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_del_thumb":
        save_master(custom_thumbnail=None)
        await query.answer("Thumbnail removed!")
        return await callbacks(client, type("Q", (), {"data": "custom_thumbnail", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "m_set_thumb":
        cancel_user_listeners(client, user_id, user_id)
        sess_token = start_user_session(user_id, "m_thumb")
        await query.answer()
        await query.message.reply("🖼️ <b>Send a photo to set as Custom Thumbnail:</b>\n\n<i>Send /cancel to abort.</i>")
        async def _thumb_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Timeout. Process cancelled.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            if ans.photo:
                save_master(custom_thumbnail=ans.photo.file_id)
                clear_user_session(user_id)
                await client.send_message(user_id, "✅ <b>Custom Thumbnail saved!</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_thumbnail")]]))
            else:
                await client.send_message(user_id, "❌ <b>Please send a photo!</b>")
                clear_user_session(user_id)
        asyncio.create_task(_thumb_worker())
        return

    # --- AUTO DELETE --- #
    if data in ("master_auto_delete_menu", "cset_autodelete", "cset_auto_delete_menu") or data.startswith("m_ad_") or data.startswith("m_set_ad") or data.startswith("m_tgl_ad"):
        from settings_modules.auto_delete import handle_auto_delete_callbacks
        return await handle_auto_delete_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply)


    # --- PERMANENT LINK --- #
    if data == "master_permanent_link":
        perm_on = bool(r.get("permanent_link_enabled", True))
        status_txt = "ON ✅" if perm_on else "OFF ❌"
        tgl_btn = "DISABLE PERMANENT LINK" if perm_on else "ENABLE PERMANENT LINK"
        text = (
            "♾️ <b>PERMANENT LINK:</b>\n\n"
            f"• <b>STATUS:</b> <b>{status_txt}</b>\n\n"
            "<b>When enabled, generated file links do not expire.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_perm")],
            [InlineKeyboardButton("‹ BACK", callback_data="settings")]
        ]))

    if data == "m_tgl_perm":
        new_s = not bool(r.get("permanent_link_enabled", True))
        save_master(permanent_link_enabled=new_s)
        await query.answer(f"Permanent links {'Enabled' if new_s else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "master_permanent_link", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    # --- PROTECT CONTENT --- #
    if data == "protect_menu":
        protect = bool(r.get("protect_content", False))
        status_txt = "ON ✅" if protect else "OFF ❌"
        tgl_btn = "OFF PROTECT CONTENT" if protect else "ON PROTECT CONTENT"
        text = (
            "🔒 <b>PROTECT CONTENT:</b>\n\n"
            "<b>PROTECT CONTENT: PREVENT USERS FROM FORWARDING AND SAVING MESSAGES SENT BY THIS BOT.</b>\n\n"
            f"<b>PROTECT CONTENT - {status_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tgl_btn, callback_data="m_tgl_protect")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "m_tgl_protect":
        protect = not bool(r.get("protect_content", False))
        save_master(protect_content=protect)
        await query.answer(f"Protect Content {'Enabled' if protect else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "protect_menu", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    await query.answer()

def register(client):
    pass
