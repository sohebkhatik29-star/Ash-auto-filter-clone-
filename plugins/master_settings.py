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
from settings_modules.caption import handle_caption_callbacks
from settings_modules.thumbnail import handle_thumbnail_callbacks
from settings_modules.custom_button import handle_custom_button_callbacks
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
                m_inner.master_settings.update_one({"type": "master_config"}, {"$set": kwargs}, upsert=True)
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
    if (
        data in ("master_token_main", "master_token_verification", "master_verify_log_channel", "m_set_v_log", "m_del_v_log", "master_set_v_log", "master_del_v_log")
        or data.startswith((
            "master_token_main", "master_token_verification", "master_verify_log_channel",
            "m_set_v_log", "m_del_v_log", "m_v_", "master_del_v_log", "master_set_v_log",
            "master_v_", "master_set_v_", "master_del_v_", "m_set_v_", "m_del_v_"
        ))
    ):
        from settings_modules.token_verify import handle_token_callbacks
        def master_get_rec():
            m_inner = db()
            if target_bid and m_inner is not None:
                doc = m_inner.bots.find_one({"bot_id": int(target_bid)})
                if doc:
                    return doc
            return master_record()
        return await handle_token_callbacks(client, query, data, user_id, r, save_master, master_get_rec, cancel_user_listeners, edit_or_reply, target_bid=target_bid)

    # --- BUTTONS --- #
    if (
        data in ("custom_button", "master_custom_button", "m_btn_add", "m_btn_rem", "m_btn_see")
        or data.startswith(("custom_button:", "m_btn_add:", "m_btn_rem:", "m_btn_see:"))
    ):
        return await handle_custom_button_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply, target_bid=target_bid)

    # --- FREE USAGE LIMIT --- #
    if (
        data in ("master_free_limit_menu", "m_set_free_limit", "m_del_free_limit")
        or data.startswith(("master_free_limit_menu:", "m_set_free_limit:", "m_del_free_limit:", "master_set_free_limit:", "master_del_free_limit:"))
    ):
        from settings_modules.free_limit import handle_free_limit_callbacks
        return await handle_free_limit_callbacks(
            client, query, data, user_id, r, save_master,
            cancel_user_listeners,
            edit_or_reply, target_bid=target_bid
        )

    # --- PREMIUM PLAN --- #
    if data.startswith(("master_premium_plan", "cset_prem", "m_prem_")):
        from settings_modules.premium_plan import handle_premium_callbacks
        return await handle_premium_callbacks(
            client, query, data, user_id, r, save_master,
            lambda uid: cancel_user_listeners(client, uid, uid),
            edit_or_reply
        )

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
    if (
        data in ("link_shortener", "cset_shortener", "m_set_main_shortener", "m_del_main_shortener", "add_shortener", "delete_shortener", "set_shortlink", "delete_shortlink", "m_tgl_shortlink", "tgl_shortlink")
        or data.startswith((
            "link_shortener:", "cset_shortener:", "m_set_main_shortener:", "m_del_main_shortener:",
            "add_shortener:", "delete_shortener:", "set_shortlink:", "delete_shortlink:", "m_tgl_shortlink:", "tgl_shortlink:"
        ))
    ):
        from settings_modules.link_shortener import handle_shortener_callbacks
        return await handle_shortener_callbacks(
            client, query, data, user_id, r, save_master,
            cancel_user_listeners,
            edit_or_reply, target_bid=target_bid
        )

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
    if data in ("custom_caption", "cset_caption", "m_del_caption", "m_set_caption", "m_tgl_cap_invert", "m_tgl_cap_spoiler", "caption_invert", "caption_spoiler", "caption_delete", "caption_edit") or data.startswith(("custom_caption:", "cset_caption:", "caption_", "cset_cap_", "m_set_caption", "m_del_caption", "m_tgl_cap_")):
        return await handle_caption_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply, target_bid=target_bid)

    # --- THUMBNAIL --- #
    if (
        data in ("custom_thumbnail", "master_custom_thumbnail", "m_set_thumb", "m_del_thumb", "m_view_thumb")
        or data.startswith(("custom_thumbnail:", "m_set_thumb:", "m_del_thumb:", "m_view_thumb:"))
    ):
        return await handle_thumbnail_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply, target_bid=target_bid)

    # --- AUTO DELETE --- #
    if data.startswith(("master_auto_delete_menu", "m_ad_", "m_set_ad", "m_tgl_ad", "cset_auto_delete", "cset_ad_", "cset_tgl_ad", "cset_set_ad", "cset_autodelete")):
        from settings_modules.auto_delete import handle_auto_delete_callbacks
        return await handle_auto_delete_callbacks(client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply, target_bid=target_bid)


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
    if data in ("protect_menu", "m_tgl_protect") or data.startswith(("protect_menu:", "m_tgl_protect:")):
        from settings_modules.protect_content import handle_protect_content_callbacks
        return await handle_protect_content_callbacks(
            client, query, data, user_id, r, save_master, cancel_user_listeners, edit_or_reply
        )

    await query.answer()

def register(client):
    pass
