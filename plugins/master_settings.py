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
    parse_time_string, format_time_minutes, is_user_premium
)
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
    if getattr(msg, "photo", None) or getattr(msg, "media", None):
        try:
            return await msg.edit_caption(caption=text, reply_markup=reply_markup)
        except Exception:
            try:
                await msg.delete()
            except Exception:
                pass
            return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    else:
        try:
            return await msg.edit_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
        except Exception:
            return await msg.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)

# ----------------- MARKUPS & MENUS ----------------- #

def master_settings_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PREMIUM PLAN", callback_data="master_premium_plan")],
        [InlineKeyboardButton("🎟️ FREE USAGE LIMIT", callback_data="master_free_limit_menu")],
        [InlineKeyboardButton("🌍 REFER AND EARN", callback_data="master_refer_earn")],
        [InlineKeyboardButton("🔗 LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("⏰ TOKEN VERIFICATION", callback_data="master_token_main")],
        [InlineKeyboardButton("📢 FORCE SUBSCRIBE", callback_data="master_fsub_menu")],
        [InlineKeyboardButton("🍿 CAPTION", callback_data="custom_caption"), InlineKeyboardButton("🖼️ THUMBNAIL", callback_data="custom_thumbnail")],
        [InlineKeyboardButton("🔘 BUTTON", callback_data="custom_button"), InlineKeyboardButton("♻️ AUTO DELETE", callback_data="master_auto_delete_menu")],
        [InlineKeyboardButton("♾️ PERMANENT LINK", callback_data="master_permanent_link")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings_back")]
    ])

def manage_clones_markup(uid):
    docs = docs_for(uid)
    rows = []
    for d in docs:
        bid = int(d["bot_id"])
        name = d.get("name") or d.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"🤖 @{name} ↗", callback_data=f"manage_clone:{bid}")])
    rows.append([InlineKeyboardButton("➕ CREATE CLONE ➕", callback_data="create_clone_prompt")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings_back")])
    return InlineKeyboardMarkup(rows)

def master_token_verification_main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ FIRST VERIFICATION", callback_data="master_token_verification:1")],
        [InlineKeyboardButton("2️⃣ SECOND VERIFICATION", callback_data="master_token_verification:2")],
        [InlineKeyboardButton("3️⃣ THIRD VERIFICATION", callback_data="master_token_verification:3")],
        [InlineKeyboardButton("📢 VERIFY LOG CHANNEL", callback_data="master_verify_log_channel")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings")]
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
        [InlineKeyboardButton("‹ BACK", callback_data="master_token_main")]
    ])

# ----------------- BUTTON BUILDER WIZARD ----------------- #

async def run_master_button_builder(client, user_id, b_type: str, back_callback: str):
    sess_token = start_user_session(user_id, f"build_m_btn_{b_type}")
    target_field = "start_buttons" if b_type == "start" else ("premium_buttons" if b_type == "premium" else "custom_buttons")
    
    rows = []
    row_idx = 1
    
    while is_user_session_active(user_id, sess_token):
        count_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("1️⃣ One Button"), KeyboardButton("2️⃣ Two Buttons")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        msg_text = f"🎯 <b>ROW {row_idx}</b>\n\n<b>How many buttons do you want in this row?</b>\n\n<i>Please choose an option using the keyboard below.</i>"
        await client.send_message(
            chat_id=user_id,
            text=msg_text,
            reply_markup=count_kb
        )
        
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
                await client.send_message(
                    chat_id=user_id,
                    text="❌ <b>INVALID CHOICE</b>\n\n<i>Please select an option using the keyboard.</i>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_callback)]])
                )
        
        if not is_user_session_active(user_id, sess_token):
            return
            
        row_buttons = []
        for b_i in range(1, btn_count + 1):
            p_text = f"🔤 <b>BUTTON {b_i}</b>\n\nSend the button text.\n\n<b>Maximum length: 64 characters</b>"
            await client.send_message(chat_id=user_id, text=p_text, reply_markup=ReplyKeyboardRemove())
            b_text = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                b_text = (ans.text or "").strip()
                if b_text == "/cancel":
                    await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                if len(b_text) > 64:
                    b_text = b_text[:64]
                break
            
            p_url = f"🔗 <b>BUTTON {b_i}</b>\n\nSend the button URL.\n\n<b>Examples:</b>\nhttps://t.me/vj_botz\nhttps://google.com"
            await client.send_message(chat_id=user_id, text=p_url, reply_markup=ReplyKeyboardRemove())
            b_url = ""
            while is_user_session_active(user_id, sess_token):
                try:
                    ans = await client.listen(chat_id=user_id, timeout=120)
                except Exception:
                    await client.send_message(chat_id=user_id, text="❌ <b>Timeout. Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                b_url = (ans.text or "").strip()
                if b_url == "/cancel":
                    await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())
                    clear_user_session(user_id)
                    return
                if not (b_url.startswith("http://") or b_url.startswith("https://")):
                    await client.send_message(
                        chat_id=user_id,
                        text="❌ <b>INVALID URL</b>\n\nPlease send a valid URL starting with:\n• https://\n• http://",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_callback)]])
                    )
                    continue
                break
            
            row_buttons.append({"text": b_text, "url": b_url})
        
        style_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("🔵 Primary"), KeyboardButton("⚪ Default")],
             [KeyboardButton("🟢 Success"), KeyboardButton("🔴 Danger")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        st_text = f"🎨 <b>ROW {row_idx}</b>\n\nSelect a button style.\n\n<i>Choose one of the options below.</i>"
        await client.send_message(chat_id=user_id, text=st_text, reply_markup=style_kb)
        try:
            ans_style = await client.listen(chat_id=user_id, timeout=120)
            style_name = (ans_style.text or "Default").strip()
        except Exception:
            style_name = "Default"
            
        rows.append({"buttons": row_buttons, "style": style_name})
        
        next_row_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Yes"), KeyboardButton("❌ No")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await client.send_message(
            chat_id=user_id,
            text="➕ <b>ADD NEW ROW</b>\n\n<b>Do you want to add another row?</b>",
            reply_markup=next_row_kb
        )
        try:
            ans_more = await client.listen(chat_id=user_id, timeout=120)
            more_txt = (ans_more.text or "").strip()
        except Exception:
            more_txt = "No"
            
        if "Yes" in more_txt or "✅" in more_txt:
            row_idx += 1
            continue
        else:
            break
            
    clear_user_session(user_id)
    save_master(**{target_field: rows})
    await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED ✅</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_callback)]])
    )

# ----------------- MASTER CALLBACKS ----------------- #

async def settings(client, message):
    text = (
        "🌟 <b>AVAILABLE PLANS • 03 DAYS - 40 ...</b>\n\n"
        "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
    )
    await message.reply(text, reply_markup=master_settings_markup())

async def callbacks(client, query):
    data = query.data
    user_id = query.from_user.id
    try:
        cancel_user_listeners(client, user_id)
    except Exception:
        pass
    
    r = master_record()
    me = await client.get_me()
    
    if data in ("settings", "settings_back"):
        text = (
            "🌟 <b>AVAILABLE PLANS • 03 DAYS - 40 ...</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=master_settings_markup())

    if data in ("my_clones", "my_clone", "clone_menu"):
        text = (
            "✨ <b>CLONE MENU</b>\n\n"
            "<b>WELCOME TO YOUR CLONE BOT MANAGEMENT HUB! CUSTOMIZE YOUR BOT SETTINGS OR MANAGE ITS STATUS USING THE OPTIONS BELOW.</b>\n\n"
            "🚀 <b>QUICK COMMANDS</b>\n\n"
            "🪄 <b>/activate</b> - ACTIVATE YOUR CLONE BOT\n"
            "🗑️ <b>/delete</b> - PERMANENTLY DELETE YOUR CLONE BOT\n\n"
            "🤖 <b>BOT CUSTOMIZATION</b>\n\n"
            "📲 <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
        )
        return await edit_or_reply(query, text, reply_markup=manage_clones_markup(user_id))

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
        bot_title = me.first_name or me.username or "ALL LINK SAHRE"
        return await query.answer(f"{bot_title}\n\nTotal Verified Today - {today_count}", show_alert=True)

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

    # Free Limit
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

    # Protect & Auto Delete
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

    # Fallback
    await query.answer()

def register(client):
    client.add_handler(MessageHandler(settings, filters.command(["settings"]) & filters.private), group=2)
    client.add_handler(CallbackQueryHandler(callbacks), group=2)
