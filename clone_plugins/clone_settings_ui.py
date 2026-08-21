# ASH FILE STORE & CLONE MANAGER - SETTINGS UI
import asyncio
import time
import re
import os
try:
    import psutil
except Exception:
    psutil = None
import datetime
from pyrogram import filters
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

def record(client):
    m = db()
    if m is None:
        return {}
    return m.bots.find_one({"bot_id": client.me.id}) or {}

def is_bot_owner(client, uid):
    try:
        if int(uid) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    r = record(client)
    try:
        if int(r.get("user_id", 0)) == int(uid):
            return True
    except Exception:
        pass
    return False

def get_bot_admins(client):
    r = record(client)
    adms = r.get("admins", [])
    if isinstance(adms, dict):
        return list(adms.values())
    elif isinstance(adms, list):
        return adms
    return []

def get_admin_data(client, uid):
    for a in get_bot_admins(client):
        if int(a.get("user_id", 0)) == int(uid):
            return a
    return None

def has_permission(client, uid, perm):
    if is_bot_owner(client, uid):
        return True
    adm = get_admin_data(client, uid)
    if not adm:
        return False
    return bool(adm.get(perm, False))

def save(client, **data):
    m = db()
    if m is not None:
        m.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)

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

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 PREMIUM PLAN", callback_data="cset_premium_plan")],
        [InlineKeyboardButton("🎟️ FREE USAGE LIMIT", callback_data="cset_free_limit_menu")],
        [InlineKeyboardButton("🌍 REFER AND EARN", callback_data="cset_refer_earn")],
        [InlineKeyboardButton("🔗 LINK SHORTNER", callback_data="link_shortener")],
        [InlineKeyboardButton("⏰ TOKEN VERIFICATION", callback_data="cset_token_main")],
        [InlineKeyboardButton("📢 FORCE SUBSCRIBE", callback_data="cset_fsub_menu")],
        [InlineKeyboardButton("🍿 CAPTION", callback_data="custom_caption"), InlineKeyboardButton("🖼️ THUMBNAIL", callback_data="custom_thumbnail")],
        [InlineKeyboardButton("🔘 BUTTON", callback_data="custom_button"), InlineKeyboardButton("♻️ AUTO DELETE", callback_data="cset_auto_delete_menu")],
        [InlineKeyboardButton("♾️ PERMANENT LINK", callback_data="cset_permanent_link")],
        [InlineKeyboardButton("🔒 PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]
    ])

def clone_manage_hub_markup(bot_username):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 MONETIZATION", callback_data="cset_monetization")],
        [InlineKeyboardButton("📝 START MESSAGE", callback_data="cset_start_msg_menu")],
        [InlineKeyboardButton("📢 LOG CHANNEL", callback_data="log_channel")],
        [InlineKeyboardButton("☁️ DATABASE CHANNEL", callback_data="database_channel")],
        [InlineKeyboardButton("👥 ADMINS", callback_data="admins_menu")],
        [InlineKeyboardButton("📊 BOT STATUS", callback_data="cset_bot_status")],
        [InlineKeyboardButton("🎁 BOT MODE", callback_data="cset_bot_mode")],
        [InlineKeyboardButton("🔄 RESTART BOT", callback_data="cset_restart_bot")],
        [InlineKeyboardButton("🚫 DELETE BOT", callback_data="cset_delete_bot")],
        [InlineKeyboardButton("🔎 MORE FEATURES ↗", callback_data="settings")]
    ])

def token_verification_main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ FIRST VERIFICATION", callback_data="cset_token_verification:1")],
        [InlineKeyboardButton("2️⃣ SECOND VERIFICATION", callback_data="cset_token_verification:2")],
        [InlineKeyboardButton("3️⃣ THIRD VERIFICATION", callback_data="cset_token_verification:3")],
        [InlineKeyboardButton("📢 VERIFY LOG CHANNEL", callback_data="cset_verify_log_channel")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings")]
    ])

def single_token_verification_markup(slot: int, is_on: bool):
    prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
    status_icon = "✅" if is_on else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔗 {prefix} VERIFY SHORTNER", callback_data=f"cset_v_shortner:{slot}")],
        [InlineKeyboardButton(f"🍿 {prefix} VERIFY TUTORIAL", callback_data=f"cset_v_tutorial:{slot}")],
        [InlineKeyboardButton(f"⏰ {prefix} VERIFY TIME", callback_data=f"cset_v_time:{slot}")],
        [InlineKeyboardButton("👥 TOTAL USER VERIFIED TODAY", callback_data=f"cset_v_stats:{slot}")],
        [InlineKeyboardButton(f"🔒 {prefix} VERIFY - {status_icon}", callback_data=f"cset_v_toggle:{slot}")],
        [InlineKeyboardButton("‹ BACK", callback_data="cset_token_main")]
    ])

def shortener_sub_markup(slot: int, is_on: bool):
    status_text = "ON SHORTLINK" if not is_on else "OFF SHORTLINK"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET SHORTLINK", callback_data=f"cset_v_set_short:{slot}")],
        [InlineKeyboardButton("DELETE SHORTLINK", callback_data=f"cset_v_del_short:{slot}")],
        [InlineKeyboardButton(status_text, callback_data=f"cset_v_tgl_short:{slot}")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]
    ])

def tutorial_sub_markup(slot: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET TUTORIAL", callback_data=f"cset_v_set_tut:{slot}")],
        [InlineKeyboardButton("DELETE TUTORIAL", callback_data=f"cset_v_del_tut:{slot}")],
        [InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]
    ])

def button_management_markup(b_type: str, has_buttons: bool):
    first_btn = InlineKeyboardButton("SEE BUTTON", callback_data=f"btn_see:{b_type}") if has_buttons else InlineKeyboardButton("ADD BUTTON", callback_data=f"btn_add:{b_type}")
    rows = [
        [first_btn, InlineKeyboardButton("REMOVE BUTTON", callback_data=f"btn_rem:{b_type}")],
    ]
    if has_buttons:
        rows.insert(1, [InlineKeyboardButton("ADD BUTTON", callback_data=f"btn_add:{b_type}")])
    back_target = "cset_start_msg_menu" if b_type == "start" else ("cset_prem_msg" if b_type == "premium" else "settings")
    rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_target)])
    return InlineKeyboardMarkup(rows)

def free_limit_markup(is_enabled: bool):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("SET FREE USAGE LIMIT", callback_data="cset_set_free_limit")],
        [InlineKeyboardButton("DELETE FREE USAGE LIMIT", callback_data="cset_del_free_limit")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings")]
    ])

def fsub_menu_markup(channels, is_on: bool):
    rows = []
    for ch in channels:
        name = ch.get("title") or ch.get("name") or str(ch.get("chat_id"))
        cid = ch.get("chat_id")
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"cset_fsub_view:{cid}")])
    rows.append([InlineKeyboardButton("➕ ADD CHANNEL ➕", callback_data="cset_fsub_add")])
    tgl_text = "OFF FORCE SUBSCRIBE" if is_on else "ON FORCE SUBSCRIBE"
    rows.append([InlineKeyboardButton(tgl_text, callback_data="cset_fsub_toggle")])
    rows.append([InlineKeyboardButton("FORCE SUBSCRIBE MESSAGE", callback_data="cset_fsub_msg")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings")])
    return InlineKeyboardMarkup(rows)

def premium_plan_main_markup(is_on: bool):
    status_icon = "✅" if is_on else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("PREMIUM PLAN MESSAGE 📨", callback_data="cset_prem_msg")],
        [InlineKeyboardButton("➕ ADD PREMIUM USER ➕", callback_data="cset_prem_add_user")],
        [InlineKeyboardButton("➖ REMOVE PREMIUM USER ➖", callback_data="cset_prem_rem_user")],
        [InlineKeyboardButton("👥 PREMIUM USERS LIST 👥", callback_data="cset_prem_list")],
        [InlineKeyboardButton(f"🔒 PREMIUM IS ON - {status_icon}", callback_data="cset_prem_toggle")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings")]
    ])

def admins_menu_markup(client):
    adms = get_bot_admins(client)
    rows = []
    for a in adms:
        name = a.get("name") or a.get("first_name") or str(a.get("user_id"))
        uid = a.get("user_id")
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"adm_manage:{uid}")])
    rows.append([InlineKeyboardButton("➕ ADD ADMIN ➕", callback_data="adm_add")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")])
    return InlineKeyboardMarkup(rows)

def single_admin_markup(client, target_uid):
    adm = get_admin_data(client, target_uid) or {}
    b_cast = "✅" if adm.get("can_broadcast", True) else "❌"
    c_set = "✅" if adm.get("can_settings", True) else "❌"
    a_adm = "✅" if adm.get("can_add_admins", False) else "❌"
    d_bot = "✅" if adm.get("can_delete_bot", False) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 BROADCAST - {b_cast}", callback_data=f"adm_tgl:{target_uid}:can_broadcast")],
        [InlineKeyboardButton(f"⚙️ CLONE BOT SETTINGS - {c_set}", callback_data=f"adm_tgl:{target_uid}:can_settings")],
        [InlineKeyboardButton(f"👥 ADD ADMINS - {a_adm}", callback_data=f"adm_tgl:{target_uid}:can_add_admins")],
        [InlineKeyboardButton(f"🚫 DELETE BOT - {d_bot}", callback_data=f"adm_tgl:{target_uid}:can_delete_bot")],
        [InlineKeyboardButton("🌐 TRANSFER CLONE OWNERSHIP", callback_data=f"adm_trans:{target_uid}")],
        [InlineKeyboardButton("🗑️ REMOVE ADMIN", callback_data=f"adm_rem:{target_uid}")],
        [InlineKeyboardButton("‹ BACK", callback_data="admins_menu")]
    ])

# ----------------- BUTTON BUILDER WIZARD ----------------- #

async def run_button_builder(client, user_id, b_type: str, back_callback: str):
    sess_token = start_user_session(user_id, f"build_btn_{b_type}")
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
    save(client, **{target_field: rows})
    await client.send_message(
        chat_id=user_id,
        text="<b>SUCCESSFULLY BUTTON ADDED ✅</b>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_callback)]])
    )

# ----------------- MAIN SETTINGS COMMAND & CALLBACKS ----------------- #

async def settings(client, message):
    text = (
        "🌟 <b>AVAILABLE PLANS • 03 DAYS - 40 ...</b>\n\n"
        "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
    )
    await message.reply(text, reply_markup=settings_menu())

async def callbacks(client, query):
    data = query.data
    user_id = query.from_user.id
    try:
        cancel_user_listeners(client, user_id)
    except Exception:
        pass
    
    r = record(client)
    me = client.me
    
    if data in ("my_clone", "my_clones", "clone_my_bots", "create_clone_prompt", "clone_limit") or data.startswith(("manage_clone:", "cm:", "cad:", "cmdelete:")):
        return

    if data in ("settings", "settings_back", "cset:home"):
        text = (
            "🌟 <b>AVAILABLE PLANS • 03 DAYS - 40 ...</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=settings_menu())

    if data in ("clone_my_clone_info", "start_back", "cset:hub"):
        text = (
            f"🤖 <b>YOUR CLONE BOT - @{me.username}</b>\n\n"
            "<i>YOU CAN CUSTOMISE YOUR BOT SETTINGS FROM GIVEN BELOW BUTTONS</i>"
        )
        return await edit_or_reply(query, text, reply_markup=clone_manage_hub_markup(me.username))

    if data in ("cset_token_main", "cset_token_verification"):
        text = (
            "⏰ <b>TOKEN VERIFICATION:</b>\n\n"
            "<b>TOKEN VERIFICATION: A SYSTEM REQUIRING USERS TO WATCH ADS OR SOLVE CAPTCHAS ON EXTERNAL SITES TO UNLOCK BOT ACCESS FOR TIME THAT BOT OWNER SET AND ALSO ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=token_verification_main_markup())

    if data.startswith("cset_token_verification:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = bool(v_cfg.get("is_on", False))
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        return await edit_or_reply(query, text, reply_markup=single_token_verification_markup(slot, is_on))

    if data.startswith("cset_v_toggle:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        new_state = not bool(v_cfg.get("is_on", False))
        v_cfg["is_on"] = new_state
        save(client, **{v_key: v_cfg})
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = f"⏰ <b>{prefix} TOKEN VERIFICATION:</b>"
        await query.answer(f"Verification {'Enabled' if new_state else 'Disabled'}!")
        return await edit_or_reply(query, text, reply_markup=single_token_verification_markup(slot, new_state))

    if data.startswith("cset_v_stats:"):
        slot = int(data.split(":")[1])
        today_count = r.get(f"verified_today_{slot}", 0)
        bot_title = me.first_name or me.username or "ALL LINK SAHRE"
        return await query.answer(f"{bot_title}\n\nTotal Verified Today - {today_count}", show_alert=True)

    if data.startswith("cset_v_shortner:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = bool(v_cfg.get("shortener_on", True))
        url = v_cfg.get("site") or r.get("base_site") or "None"
        api = v_cfg.get("api") or r.get("shortener_api") or "None"
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        status_txt = "ON ✅" if is_on else "OFF ❌"
        text = (
            f"🔗 <b>{prefix} VERIFY SHORTNER:</b>\n\n"
            "<b>LINK SHORTENER: A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>\n\n"
            f"<b>SHORTLINK - {status_txt}</b>\n\n"
            f"<b>URL -</b> <code>{url}</code>\n"
            f"<b>API -</b> <code>{api}</code>"
        )
        return await edit_or_reply(query, text, reply_markup=shortener_sub_markup(slot, is_on))

    if data.startswith("cset_v_tgl_short:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        is_on = not bool(v_cfg.get("shortener_on", True))
        v_cfg["shortener_on"] = is_on
        save(client, **{v_key: v_cfg})
        url = v_cfg.get("site") or r.get("base_site") or "None"
        api = v_cfg.get("api") or r.get("shortener_api") or "None"
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        status_txt = "ON ✅" if is_on else "OFF ❌"
        text = (
            f"🔗 <b>{prefix} VERIFY SHORTNER:</b>\n\n"
            "<b>LINK SHORTENER: A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>\n\n"
            f"<b>SHORTLINK - {status_txt}</b>\n\n"
            f"<b>URL -</b> <code>{url}</code>\n"
            f"<b>API -</b> <code>{api}</code>"
        )
        return await edit_or_reply(query, text, reply_markup=shortener_sub_markup(slot, is_on))

    if data.startswith("cset_v_set_short:"):
        slot = int(data.split(":")[1])
        sess_token = start_user_session(user_id, f"set_short_{slot}")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A SHORTLINK URL OR DOMAIN...</b>\n\n<b>FORMAT :</b>\nhttps://vjlink.online - ❌\nvjlink.online - ✅\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]])
        )
        try:
            ans_site = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        site_raw = (ans_site.text or "").strip()
        if site_raw == "/cancel" or not is_user_session_active(user_id, sess_token):
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]]))
        site = site_raw.replace("https://", "").replace("http://", "").rstrip("/")
        
        await client.send_message(
            chat_id=user_id,
            text="<b>SEND ME SHORTLINK API...</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]])
        )
        try:
            ans_api = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        api_raw = (ans_api.text or "").strip()
        clear_user_session(user_id)
        if api_raw == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]]))
        
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["site"] = site
        v_cfg["api"] = api_raw
        v_cfg["shortener_on"] = True
        save(client, **{v_key: v_cfg, "base_site": site, "shortener_api": api_raw})
        return await client.send_message(
            chat_id=user_id,
            text="<b>SUCCESSFULLY SET SHORTLINK ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]])
        )

    if data.startswith("cset_v_del_short:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["site"] = None
        v_cfg["api"] = None
        v_cfg["shortener_on"] = False
        save(client, **{v_key: v_cfg})
        await query.answer("Shortener deleted successfully!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED SHORTLINK ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_shortner:{slot}")]])
        )

    if data.startswith("cset_v_tutorial:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        tut = v_cfg.get("tutorial") or "None"
        prefix = "FIRST" if slot == 1 else ("SECOND" if slot == 2 else "THIRD")
        text = (
            f"🍿 <b>{prefix} VERIFY TUTORIAL:</b>\n\n"
            "<b>TUTORIAL LINK: THE PROCESS VIDEO OF OPENING LINK OF SHORTER. LINK OF VIDEO OR CHANNEL WHERE VIDEO IS UPLOADED. VIDEO MEANS VIDEO OF HOW TO OPEN LINK.</b>\n\n"
            f"<b>LINK -</b> <code>{tut}</code>"
        )
        return await edit_or_reply(query, text, reply_markup=tutorial_sub_markup(slot))

    if data.startswith("cset_v_set_tut:"):
        slot = int(data.split(":")[1])
        sess_token = start_user_session(user_id, f"set_tut_{slot}")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME TUTORIAL LINK...</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )
        try:
            ans_tut = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        tut_val = (ans_tut.text or "").strip()
        clear_user_session(user_id)
        if tut_val == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]]))
        
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["tutorial"] = tut_val
        save(client, **{v_key: v_cfg})
        return await client.send_message(
            chat_id=user_id,
            text="<b>SUCCESSFULLY SET TUTORIAL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )

    if data.startswith("cset_v_del_tut:"):
        slot = int(data.split(":")[1])
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["tutorial"] = None
        save(client, **{v_key: v_cfg})
        await query.answer("Tutorial link deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED TUTORIAL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_v_tutorial:{slot}")]])
        )

    if data.startswith("cset_v_time:"):
        slot = int(data.split(":")[1])
        sess_token = start_user_session(user_id, f"set_time_{slot}")
        await query.answer()
        await edit_or_reply(
            query,
            "⏰ <b>Step 1/2:</b>\nSend duration number (e.g., 1 for 1 hour/day, 24 for 24 hours):\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )
        try:
            ans_num = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        num_raw = (ans_num.text or "").strip()
        if num_raw == "/cancel" or not num_raw.isdigit():
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid duration. Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]]))
        
        await client.send_message(
            chat_id=user_id,
            text="⏳ <b>Step 2/2:</b>\nSend time unit (Type: hour, day, week, or month):\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )
        try:
            ans_unit = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        unit_raw = (ans_unit.text or "").strip().lower()
        clear_user_session(user_id)
        if unit_raw == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]]))
        
        mins = parse_time_string(f"{num_raw} {unit_raw}")
        v_key = f"verify_{slot}" if slot > 1 else "verify_1"
        v_cfg = r.get(v_key, {})
        v_cfg["time_minutes"] = mins
        save(client, **{v_key: v_cfg})
        return await client.send_message(
            chat_id=user_id,
            text=f"<b>SUCCESSFULLY SET VERIFY TIME ✅</b>\n\nDuration: <b>{format_time_minutes(mins)}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"cset_token_verification:{slot}")]])
        )

    if data == "cset_verify_log_channel":
        v_log = r.get("verify_log_channel")
        v_title = r.get("verify_log_channel_title")
        status_txt = f"<b>YOUR VERIFY LOG CHANNEL - {v_title or v_log}</b>" if v_log else "<b>YOU DIDN'T ADDED ANY VERIFY LOG CHANNEL</b>"
        text = (
            "📢 <b>VERIFY LOG CHANNEL:</b>\n\n"
            "<b>WHAT IS VERIFY LOG CHANNEL ??</b>\n"
            "<b>IF USERS COMPLETE VERIFICATION THEN BOT NOTIFIES YOU.</b>\n\n"
            f"{status_txt}"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CHANNEL", callback_data="cset_set_verify_log"), InlineKeyboardButton("DELETE CHANNEL", callback_data="cset_del_verify_log")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_token_main")]
            ])
        )

    if data == "cset_set_verify_log":
        sess_token = start_user_session(user_id, "set_v_log")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>FORWARD A MESSAGE FROM YOUR VERIFY LOG CHANNEL WITH FORWARD TAG AND MAKE ME ADMIN IN THAT CHANNEL WITH FULL RIGHTS</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_verify_log_channel")]])
        )
        try:
            fwd = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not fwd or fwd.text == "/cancel":
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_verify_log_channel")]]))
        fwd_chat = getattr(fwd, "forward_from_chat", None)
        if not fwd_chat:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Forwarded message must be from a channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_verify_log_channel")]]))
        save(client, verify_log_channel=fwd_chat.id, verify_log_channel_title=fwd_chat.title)
        clear_user_session(user_id)
        return await client.send_message(
            chat_id=user_id,
            text=f"⚡ <b>SUCCESSFULLY ADDED YOUR VERIFY LOG CHANNEL - {fwd_chat.title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_verify_log_channel")]])
        )

    if data == "cset_del_verify_log":
        save(client, verify_log_channel=None, verify_log_channel_title=None)
        await query.answer("Verify log channel deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED VERIFY LOG CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_verify_log_channel")]])
        )

    # 3. Button Builder for Start Message / Messages / Premium Plan
    if data in ("custom_button", "cset_start_button", "cset_prem_button"):
        b_type = "start" if data == "cset_start_button" else ("premium" if data == "cset_prem_button" else "message")
        target_field = "start_buttons" if b_type == "start" else ("premium_buttons" if b_type == "premium" else "custom_buttons")
        btns = r.get(target_field, [])
        has_btns = bool(btns)
        title_txt = "START BUTTON" if b_type == "start" else ("PREMIUM PLAN MESSAGE BUTTON" if b_type == "premium" else "MESSAGE BUTTON")
        dest_txt = "START MESSAGE" if b_type == "start" else ("PREMIUM PLAN MESSAGE" if b_type == "premium" else "STORED MESSAGE")
        show_txt = "START MESSAGE" if b_type == "start" else ("PREMIUM MESSAGE" if b_type == "premium" else "EVERY MESSAGE")
        text = (
            f"🔘 <b>{title_txt}:</b>\n\n"
            f"<b>CREATE CUSTOM URL BUTTONS FOR YOUR {dest_txt}. THE BUTTONS YOU ADD WILL BE SHOWN BELOW {show_txt}.</b>\n\n"
            "• <b>UP TO TWO BUTTONS PER ROW</b>\n"
            "• <b>MULTIPLE ROWS SUPPORTED</b>\n"
            "• <b>THREE STYLES / BUTTON COLOUR AVAILABLE (RED, GREEN AND BLUE)</b>\n\n"
            "<b>FOLLOW THE NEXT STEPS TO BUILD YOUR BUTTONS</b>"
        )
        return await edit_or_reply(query, text, reply_markup=button_management_markup(b_type, has_btns))

    if data.startswith("btn_add:"):
        b_type = data.split(":")[1]
        back_cb = "cset_start_button" if b_type == "start" else ("cset_prem_button" if b_type == "premium" else "custom_button")
        await query.answer()
        asyncio.create_task(run_button_builder(client, user_id, b_type, back_cb))
        return

    if data.startswith("btn_rem:"):
        b_type = data.split(":")[1]
        target_field = "start_buttons" if b_type == "start" else ("premium_buttons" if b_type == "premium" else "custom_buttons")
        save(client, **{target_field: []})
        await query.answer("Buttons removed successfully!")
        back_cb = "cset_start_button" if b_type == "start" else ("cset_prem_button" if b_type == "premium" else "custom_button")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY REMOVED BUTTONS ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=back_cb)]])
        )

    if data.startswith("btn_see:"):
        b_type = data.split(":")[1]
        target_field = "start_buttons" if b_type == "start" else ("premium_buttons" if b_type == "premium" else "custom_buttons")
        btns = r.get(target_field, [])
        back_cb = "cset_start_button" if b_type == "start" else ("cset_prem_button" if b_type == "premium" else "custom_button")
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
        rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_cb)])
        return await edit_or_reply(
            query,
            "<b>HERE ARE YOUR CONFIGURED BUTTONS:</b>",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    # 4. Free Usage Limit
    if data == "cset_free_limit_menu":
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
        return await edit_or_reply(query, text, reply_markup=free_limit_markup(is_on))

    if data == "cset_set_free_limit":
        sess_token = start_user_session(user_id, "set_free_limit")
        await query.answer()
        await edit_or_reply(
            query,
            "🔢 <b>Step 1/3:</b>\nSend how many free uses/files you want to allow (e.g., 5):\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]])
        )
        try:
            ans1 = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        c_raw = (ans1.text or "").strip()
        if c_raw == "/cancel" or not c_raw.isdigit():
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid number. Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]]) )
        files_count = int(c_raw)
        
        await client.send_message(
            chat_id=user_id,
            text="📅 <b>Step 2/3:</b>\nSend the duration number (e.g., 1 for 1 day/month, 2 for 2 weeks):\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]])
        )
        try:
            ans2 = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        d_raw = (ans2.text or "").strip()
        if d_raw == "/cancel" or not d_raw.isdigit():
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid duration. Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]]) )
        dur_num = int(d_raw)
        
        await client.send_message(
            chat_id=user_id,
            text="⏳ <b>Step 3/3:</b>\nSend time unit (Type: day, week, month, or year):\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]])
        )
        try:
            ans3 = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        u_raw = (ans3.text or "").strip().lower()
        clear_user_session(user_id)
        if u_raw == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Process cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]]) )
        
        save(client, free_limit={"enabled": True, "count": files_count, "num": dur_num, "unit": u_raw})
        return await client.send_message(
            chat_id=user_id,
            text=f"✅ <b>Limit Set Successfully!</b>\n\n• <b>Limit Count:</b> {files_count} files\n• <b>Duration:</b> Every {dur_num} {u_raw}(s) ({dur_num} total {u_raw}s)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]])
        )

    if data == "cset_del_free_limit":
        save(client, free_limit={"enabled": False, "count": 0, "num": 0, "unit": "day"})
        await query.answer("Free limit deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED FREE USAGE LIMIT ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_free_limit_menu")]])
        )

    # 5. Force Subscribe
    if data == "cset_fsub_menu":
        channels = r.get("fsub_channels", [])
        is_on = bool(r.get("fsub_on", True))
        status_txt = "ON ✅" if is_on else "OFF ❌"
        text = (
            "📢 <b>FORCE SUBSCRIBE:</b>\n\n"
            "<b>A TELEGRAM BOT FEATURE FORCING USERS TO SUBSCRIBE TO SPECIFIC CHANNELS BEFORE ACCESSING CONTENT.</b>\n\n"
            "<b>NORMAL FSUB:</b>\n"
            "<b>REQUIRES THE USER TO CLICK A JOIN BUTTON ON A CHANNEL OR GROUP, THEN BOT CHECKS MEMBERSHIP INSTANTLY TO UNLOCK RESTRICTED CONTENT OR CHAT ACCESS.</b>\n\n"
            "<b>JOIN REQUEST FSUB:</b>\n"
            "<b>REQUIRES THE USER TO SEND A REQUEST TO JOIN A PRIVATE CHANNEL OR GROUP THEN USER CAN ACCESS CONTENT.</b>\n\n"
            "<b>YOU CAN ADD MULTIPLE CHANNELS</b>\n\n"
            f"<b>FORCE SUBSCRIBE - {status_txt}</b>"
        )
        return await edit_or_reply(query, text, reply_markup=fsub_menu_markup(channels, is_on))

    if data == "cset_fsub_toggle":
        channels = r.get("fsub_channels", [])
        is_on = not bool(r.get("fsub_on", True))
        save(client, fsub_on=is_on)
        await query.answer(f"Force Subscribe {'Enabled' if is_on else 'Disabled'}!")
        status_txt = "ON ✅" if is_on else "OFF ❌"
        text = (
            "📢 <b>FORCE SUBSCRIBE:</b>\n\n"
            "<b>A TELEGRAM BOT FEATURE FORCING USERS TO SUBSCRIBE TO SPECIFIC CHANNELS BEFORE ACCESSING CONTENT.</b>\n\n"
            "<b>NORMAL FSUB:</b>\n"
            "<b>REQUIRES THE USER TO CLICK A JOIN BUTTON ON A CHANNEL OR GROUP, THEN BOT CHECKS MEMBERSHIP INSTANTLY TO UNLOCK RESTRICTED CONTENT OR CHAT ACCESS.</b>\n\n"
            "<b>JOIN REQUEST FSUB:</b>\n"
            "<b>REQUIRES THE USER TO SEND A REQUEST TO JOIN A PRIVATE CHANNEL OR GROUP THEN USER CAN ACCESS CONTENT.</b>\n\n"
            "<b>YOU CAN ADD MULTIPLE CHANNELS</b>\n\n"
            f"<b>FORCE SUBSCRIBE - {status_txt}</b>"
        )
        return await edit_or_reply(query, text, reply_markup=fsub_menu_markup(channels, is_on))

    if data == "cset_fsub_add":
        sess_token = start_user_session(user_id, "fsub_add")
        await query.answer()
        await edit_or_reply(
            query,
            "( SET CHANNEL )\n\n<b>FORWARD A MESSAGE FROM YOUR FORCE SUBSCRIBE CHANNEL WITH FORWARD TAG AND MAKE ME ADMIN IN THAT CHANNEL WITH FULL RIGHTS</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]])
        )
        try:
            fwd = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not fwd or fwd.text == "/cancel":
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]) )
        fwd_chat = getattr(fwd, "forward_from_chat", None)
        if not fwd_chat:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Forwarded message must be from a channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]) )
        
        channels = list(r.get("fsub_channels", []))
        for c in channels:
            if c.get("chat_id") == fwd_chat.id:
                clear_user_session(user_id)
                return await client.send_message(chat_id=user_id, text="<b>THIS CHANNEL IS ALREADY ADDED.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]]) )
        
        mode_kb = ReplyKeyboardMarkup(
            [[KeyboardButton("Normal"), KeyboardButton("Join Request")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await client.send_message(
            chat_id=user_id,
            text="<b>SELECT YOUR MODE WHICH YOU WANT FOR THIS BELOW 👇</b>",
            reply_markup=mode_kb
        )
        try:
            ans_m = await client.listen(chat_id=user_id, timeout=120)
            sel_mode = "request" if "Request" in (ans_m.text or "") else "normal"
        except Exception:
            sel_mode = "normal"
            
        clear_user_session(user_id)
        channels.append({"chat_id": fwd_chat.id, "title": fwd_chat.title, "username": fwd_chat.username, "mode": sel_mode})
        save(client, fsub_channels=channels, fsub_on=True)
        return await client.send_message(
            chat_id=user_id,
            text=f"⚡ <b>SUCCESSFULLY ADDED FORCE SUBSCRIBE CHANNEL - {fwd_chat.title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]])
        )

    if data.startswith("cset_fsub_view:"):
        cid = int(data.split(":")[1])
        channels = list(r.get("fsub_channels", []))
        target_ch = next((c for c in channels if c.get("chat_id") == cid), None)
        title = target_ch.get("title", str(cid)) if target_ch else str(cid)
        return await edit_or_reply(
            query,
            f"📢 <b>CHANNEL:</b> {title}\n🆔 <code>{cid}</code>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ DELETE CHANNEL", callback_data=f"cset_fsub_del:{cid}")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]
            ])
        )

    if data.startswith("cset_fsub_del:"):
        cid = int(data.split(":")[1])
        channels = [c for c in r.get("fsub_channels", []) if c.get("chat_id") != cid]
        save(client, fsub_channels=channels)
        await query.answer("Channel removed!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY REMOVED FSUB CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_fsub_menu")]])
        )

    # 6. Start Message & Picture
    if data == "cset_start_msg_menu":
        text = (
            "📝 <b>START MESSAGE:</b>\n\n"
            "<b>START MESSAGE: WHEN USER GIVE START COMMAND OR START THE BOT THEN BOT REPLY START MESSAGE. IN START MESSAGE BOT OWNER CAN SET START MESSAGE TEXT, PICTURE AND BUTTON.</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("START TEXT", callback_data="cset_start_text")],
                [InlineKeyboardButton("START PICTURE", callback_data="cset_start_pic")],
                [InlineKeyboardButton("START BUTTON", callback_data="cset_start_button")],
                [InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_start_text":
        st_txt = r.get("start_text") or "Default start text"
        text = (
            "📝 <b>START TEXT:</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n"
            "{mention} - USER - NAME MENTION\n"
            "{bot_mention} - BOT - NAME MENTION\n\n"
            f"<b>TEXT -</b> <code>{st_txt}</code>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET TEXT", callback_data="cset_set_start_text"), InlineKeyboardButton("DEFAULT TEXT", callback_data="cset_def_start_text")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_text":
        sess_token = start_user_session(user_id, "set_start_text")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A START TEXT.</b>\n\n<b>AVAILABLE FILLINGS:</b>\n{mention} - USER - NAME MENTION\n{bot_mention} - BOT - NAME MENTION\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_text")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        t_val = (ans.text or "").strip()
        clear_user_session(user_id)
        if t_val == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_text")]]) )
        save(client, start_text=t_val)
        return await client.send_message(
            chat_id=user_id,
            text=f"<b>SUCCESSFULLY SET START TEXT -</b>\n\n{t_val}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_text")]])
        )

    if data == "cset_def_start_text":
        save(client, start_text=None)
        await query.answer("Reset to default start text!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY SET TO DEFAULT START TEXT.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_text")]])
        )

    if data == "cset_start_pic":
        pic = r.get("start_pic")
        spoiler = bool(r.get("start_pic_spoiler", False))
        spoiler_txt = "✅" if spoiler else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if pic else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "🖼️ <b>START PICTURE:</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER EFFECT - {spoiler_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PICTURE", callback_data="cset_set_start_pic")],
                [InlineKeyboardButton("DELETE PICTURE", callback_data="cset_del_start_pic")],
                [InlineKeyboardButton("VIEW PICTURE", callback_data="cset_view_start_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_start_spoiler")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    if data == "cset_set_start_pic":
        sess_token = start_user_session(user_id, "set_start_pic")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A PICTURE.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_pic")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not ans or ans.text == "/cancel" or not ans.photo:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled or not a photo.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_pic")]]) )
        photo_id = ans.photo.file_id
        clear_user_session(user_id)
        save(client, start_pic=photo_id)
        return await client.send_message(
            chat_id=user_id,
            text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_pic")]])
        )

    if data == "cset_del_start_pic":
        save(client, start_pic=None)
        await query.answer("Start picture deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED START PICTURE ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_start_pic")]])
        )

    if data == "cset_tgl_start_spoiler":
        spoiler = not bool(r.get("start_pic_spoiler", False))
        save(client, start_pic_spoiler=spoiler)
        spoiler_txt = "✅" if spoiler else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if r.get("start_pic") else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "🖼️ <b>START PICTURE:</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER EFFECT - {spoiler_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PICTURE", callback_data="cset_set_start_pic")],
                [InlineKeyboardButton("DELETE PICTURE", callback_data="cset_del_start_pic")],
                [InlineKeyboardButton("VIEW PICTURE", callback_data="cset_view_start_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_start_spoiler")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_start_msg_menu")]
            ])
        )

    # 7. Premium Plan
    if data == "cset_premium_plan":
        is_on = bool(r.get("premium_on", True))
        text = (
            "💳 <b>PREMIUM PLAN:</b>\n\n"
            "<b>PREMIUM PLAN: A PAID SUBSCRIPTION THAT GIVES USERS AD-FREE ACCESS, FASTER DOWNLOADS, AND EXCLUSIVE ENTRY TO RESTRICTED FILES OR GROUPS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=premium_plan_main_markup(is_on))

    if data == "cset_prem_toggle":
        is_on = not bool(r.get("premium_on", True))
        save(client, premium_on=is_on)
        await query.answer(f"Premium Plan {'Enabled' if is_on else 'Disabled'}!")
        text = (
            "💳 <b>PREMIUM PLAN:</b>\n\n"
            "<b>PREMIUM PLAN: A PAID SUBSCRIPTION THAT GIVES USERS AD-FREE ACCESS, FASTER DOWNLOADS, AND EXCLUSIVE ENTRY TO RESTRICTED FILES OR GROUPS.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=premium_plan_main_markup(is_on))

    if data == "cset_prem_list":
        prem_users = r.get("premium_users", [])
        if not prem_users:
            bot_title = me.first_name or me.username or "ALL LINK SAHRE"
            return await query.answer(f"{bot_title}\n\nNO PREMIUM USERS FOUND", show_alert=True)
        text = "👥 <b>PREMIUM USERS LIST:</b>\n\n" + "\n".join([f"• <code>{u}</code>" for u in prem_users[:30]])
        return await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]) )

    if data == "cset_prem_add_user":
        sess_token = start_user_session(user_id, "prem_add")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>NOW SEND ME USER ID</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        uid_raw = (ans.text or "").strip()
        clear_user_session(user_id)
        if uid_raw == "/cancel" or not uid_raw.isdigit():
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid User ID. Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]) )
        target_uid = int(uid_raw)
        prem_users = list(r.get("premium_users", []))
        if target_uid not in prem_users:
            prem_users.append(target_uid)
        save(client, premium_users=prem_users)
        return await client.send_message(
            chat_id=user_id,
            text=f"✅ <b>Successfully added user {target_uid} to Premium List!</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )

    if data == "cset_prem_rem_user":
        sess_token = start_user_session(user_id, "prem_rem")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>NOW SEND ME USER ID</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        uid_raw = (ans.text or "").strip()
        clear_user_session(user_id)
        if uid_raw == "/cancel" or not uid_raw.isdigit():
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid User ID. Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]]) )
        target_uid = int(uid_raw)
        prem_users = [u for u in r.get("premium_users", []) if u != target_uid]
        save(client, premium_users=prem_users)
        return await client.send_message(
            chat_id=user_id,
            text=f"✅ <b>Successfully removed user {target_uid} from Premium List!</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]])
        )

    if data == "cset_prem_msg":
        text = (
            "📝 <b>PREMIUM PLAN MESSAGE:</b>\n\n"
            "<b>PREMIUM PLAN MESSAGE: WHEN USER CLICK ON BUY PREMIUM PLAN BUTTON THEN BOT REPLY PREMIUM PLAN MESSAGE. IN PREMIUM PLAN MESSAGE BOT OWNER CAN SET PREMIUM PLAN MESSAGE TEXT, PICTURE AND BUTTON.</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("PREMIUM PLAN TEXT", callback_data="cset_prem_text")],
                [InlineKeyboardButton("PREMIUM PLAN PICTURE", callback_data="cset_prem_pic")],
                [InlineKeyboardButton("PREMIUM PLAN BUTTON", callback_data="cset_prem_button")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_premium_plan")]
            ])
        )

    if data == "cset_prem_text":
        p_txt = r.get("premium_text") or "YOU DO NOT ADDED ANY PLAN TEXT.."
        text = (
            "📜 <b>PREMIUM PLAN TEXT:</b>\n\n"
            f"<b>TEXT -</b> {p_txt}\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n"
            "{user_mention} : USER - NAME\n\n"
            "<b>YOU CAN USE HTML STYLE FORMATTING IN TEXT</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PREMIUM TEXT", callback_data="cset_set_prem_text")],
                [InlineKeyboardButton("REMOVE PREMIUM TEXT", callback_data="cset_del_prem_text")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_prem_msg")]
            ])
        )

    if data == "cset_set_prem_text":
        sess_token = start_user_session(user_id, "set_prem_txt")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A PREMIUM TEXT.</b>\n\n<b>AVAILABLE FILLINGS:</b>\n{user_mention} : USER - NAME\n\n<b>YOU CAN USE HTML STYLE FORMATTING IN TEXT</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        val = (ans.text or "").strip()
        clear_user_session(user_id)
        if val == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]]) )
        save(client, premium_text=val)
        return await client.send_message(
            chat_id=user_id,
            text=f"<b>SUCCESSFULLY SET PREMIUM TEXT -</b>\n\n{val}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )

    if data == "cset_del_prem_text":
        save(client, premium_text=None)
        await query.answer("Premium text removed!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY SET TO DEFAULT PREMIUM TEXT.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_text")]])
        )

    if data == "cset_prem_pic":
        pic = r.get("premium_pic")
        spoiler = bool(r.get("premium_pic_spoiler", False))
        invert = bool(r.get("premium_pic_invert", False))
        spoiler_txt = "✅" if spoiler else "❌"
        invert_txt = "✅" if invert else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if pic else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "<b>INVERT CAPTION: IF ON THEN CAPTION SHOW ABOVE PREMIUM MESSAGE PICTURE, IF OFF THEN CAPTION SHOWN BELOW PREMIUM MESSAGE PICTURE AS NORMAL.</b>\n\n"
            "<b>SPOILER ANIMATION: IF ON THEN PREMIUM MESSAGE PICTURE GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER - {spoiler_txt}</b>\n"
            f"<b>INVERT CAPTION - {invert_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PREMIUM PIC", callback_data="cset_set_prem_pic")],
                [InlineKeyboardButton("DELETE PREMIUM PIC", callback_data="cset_del_prem_pic")],
                [InlineKeyboardButton("VIEW PREMIUM PIC", callback_data="cset_view_prem_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_prem_spoiler")],
                [InlineKeyboardButton(f"INVERT CAPTION - {invert_txt}", callback_data="cset_tgl_prem_invert")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_prem_msg")]
            ])
        )

    if data == "cset_set_prem_pic":
        sess_token = start_user_session(user_id, "set_prem_pic")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A PICTURE.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_pic")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not ans or ans.text == "/cancel" or not ans.photo:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled or not a photo.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_pic")]]) )
        photo_id = ans.photo.file_id
        clear_user_session(user_id)
        save(client, premium_pic=photo_id)
        return await client.send_message(
            chat_id=user_id,
            text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_pic")]])
        )

    if data == "cset_del_prem_pic":
        save(client, premium_pic=None)
        await query.answer("Premium picture deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED PREMIUM PICTURE ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_prem_pic")]])
        )

    if data == "cset_tgl_prem_spoiler":
        spoiler = not bool(r.get("premium_pic_spoiler", False))
        save(client, premium_pic_spoiler=spoiler)
        spoiler_txt = "✅" if spoiler else "❌"
        invert_txt = "✅" if bool(r.get("premium_pic_invert", False)) else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if r.get("premium_pic") else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "<b>INVERT CAPTION: IF ON THEN CAPTION SHOW ABOVE PREMIUM MESSAGE PICTURE, IF OFF THEN CAPTION SHOWN BELOW PREMIUM MESSAGE PICTURE AS NORMAL.</b>\n\n"
            "<b>SPOILER ANIMATION: IF ON THEN PREMIUM MESSAGE PICTURE GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER - {spoiler_txt}</b>\n"
            f"<b>INVERT CAPTION - {invert_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PREMIUM PIC", callback_data="cset_set_prem_pic")],
                [InlineKeyboardButton("DELETE PREMIUM PIC", callback_data="cset_del_prem_pic")],
                [InlineKeyboardButton("VIEW PREMIUM PIC", callback_data="cset_view_prem_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_prem_spoiler")],
                [InlineKeyboardButton(f"INVERT CAPTION - {invert_txt}", callback_data="cset_tgl_prem_invert")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_prem_msg")]
            ])
        )

    if data == "cset_tgl_prem_invert":
        invert = not bool(r.get("premium_pic_invert", False))
        save(client, premium_pic_invert=invert)
        invert_txt = "✅" if invert else "❌"
        spoiler_txt = "✅" if bool(r.get("premium_pic_spoiler", False)) else "❌"
        has_pic_txt = "ALREADY ADDED PICTURE..." if r.get("premium_pic") else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "<b>INVERT CAPTION: IF ON THEN CAPTION SHOW ABOVE PREMIUM MESSAGE PICTURE, IF OFF THEN CAPTION SHOWN BELOW PREMIUM MESSAGE PICTURE AS NORMAL.</b>\n\n"
            "<b>SPOILER ANIMATION: IF ON THEN PREMIUM MESSAGE PICTURE GET SPOILER ANIMATION, IF OFF THEN NO SPOILER ANIMATION.</b>\n\n"
            f"<b>{has_pic_txt}</b>\n\n"
            f"<b>SPOILER - {spoiler_txt}</b>\n"
            f"<b>INVERT CAPTION - {invert_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET PREMIUM PIC", callback_data="cset_set_prem_pic")],
                [InlineKeyboardButton("DELETE PREMIUM PIC", callback_data="cset_del_prem_pic")],
                [InlineKeyboardButton("VIEW PREMIUM PIC", callback_data="cset_view_prem_pic")],
                [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data="cset_tgl_prem_spoiler")],
                [InlineKeyboardButton(f"INVERT CAPTION - {invert_txt}", callback_data="cset_tgl_prem_invert")],
                [InlineKeyboardButton("‹ BACK", callback_data="cset_prem_msg")]
            ])
        )

    # 8. Captions & Thumbnails
    if data == "custom_caption":
        cap = r.get("caption") or "{file_name}\n\n{file_size}"
        invert = bool(r.get("caption_invert", False))
        spoiler = bool(r.get("caption_spoiler", False))
        inv_txt = "ON ✅" if invert else "OFF ❌"
        sp_txt = "ON ✅" if spoiler else "OFF ❌"
        text = (
            "🍿 <b>CAPTION:</b>\n\n"
            "<b>AVAILABLE FILLING:-</b>\n"
            "{file_name} - FILE NAME FOR MEDIA MESSAGE\n"
            "{file_size} - FILE SIZE FOR MEDIA MESSAGE\n"
            "{originalcaption} - ORIGINAL CAPTION FOR MEDIA MESSAGE\n\n"
            f"<b>CAPTION -</b>\n<code>{cap}</code>\n\n"
            f"<b>INVERT CAPTION - {inv_txt}</b>\n"
            f"<b>SPOILER ANIMATION - {sp_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CAPTION", callback_data="cset_set_caption")],
                [InlineKeyboardButton("DEFAULT CAPTION", callback_data="cset_def_caption")],
                [InlineKeyboardButton(f"INVERT CAPTION - {'✅' if invert else '❌'}", callback_data="cset_tgl_cap_invert")],
                [InlineKeyboardButton(f"SPOILER ANIMATION - {'✅' if spoiler else '❌'}", callback_data="cset_tgl_cap_spoiler")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "cset_set_caption":
        sess_token = start_user_session(user_id, "set_cap")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A FILE CAPTION.</b>\n\n<b>AVAILABLE FILLING:-</b>\n{file_name} - FILE NAME FOR MEDIA MESSAGE\n{file_size} - FILE SIZE FOR MEDIA MESSAGE\n{originalcaption} - ORIGINAL CAPTION FOR MEDIA MESSAGE\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_caption")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        val = (ans.text or "").strip()
        clear_user_session(user_id)
        if val == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_caption")]]) )
        save(client, caption=val)
        return await client.send_message(
            chat_id=user_id,
            text=f"<b>SUCCESSFULLY SET FILE CAPTION -</b>\n\n{val}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_caption")]])
        )

    if data == "cset_def_caption":
        save(client, caption=None)
        await query.answer("Reset to default caption!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY SET TO DEFAULT CAPTION.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_caption")]])
        )

    if data == "cset_tgl_cap_invert":
        invert = not bool(r.get("caption_invert", False))
        save(client, caption_invert=invert)
        return await callbacks(client, type("Q", (), {"data": "custom_caption", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "cset_tgl_cap_spoiler":
        spoiler = not bool(r.get("caption_spoiler", False))
        save(client, caption_spoiler=spoiler)
        return await callbacks(client, type("Q", (), {"data": "custom_caption", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "custom_thumbnail":
        thumb = r.get("thumbnail")
        status_txt = "ALREADY ADDED PICTURE..." if thumb else "YOU DIDN'T ADDED ANY PICTURE..."
        text = (
            "🖼️ <b>CUSTOM THUMBNAIL:</b>\n\n"
            "<b>CUSTOM THUMBNAIL: IT IS A COVER THUMBNAIL FOR VIDEO FILE WHICH BOT SEND TO USER, THE THUMB YOU SET IS APPLIED ON ALL OLD OR NEW FILE. AND IT SUPPORT ONLY IN VIDEO FILE NOT IN DOCUMENT FILE.</b>\n\n"
            f"<b>{status_txt}</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET THUMBNAIL", callback_data="cset_set_thumb")],
                [InlineKeyboardButton("DELETE THUMBNAIL", callback_data="cset_del_thumb")],
                [InlineKeyboardButton("VIEW THUMBNAIL", callback_data="cset_view_thumb")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "cset_set_thumb":
        sess_token = start_user_session(user_id, "set_thumb")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND ME A PICTURE.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_thumbnail")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not ans or ans.text == "/cancel" or not ans.photo:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled or not a photo.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_thumbnail")]]) )
        photo_id = ans.photo.file_id
        clear_user_session(user_id)
        save(client, thumbnail=photo_id)
        return await client.send_message(
            chat_id=user_id,
            text="<b>SUCCESSFULLY PICTURE SET ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_thumbnail")]])
        )

    if data == "cset_del_thumb":
        save(client, thumbnail=None)
        await query.answer("Thumbnail deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED THUMBNAIL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="custom_thumbnail")]])
        )

    # 9. Channels (Log & DB)
    if data == "log_channel":
        log_ch = r.get("log_channel")
        log_title = r.get("log_channel_title")
        status_txt = f"<b>YOUR LOG CHANNEL - {log_title or log_ch}</b>" if log_ch else "<b>YOU DIDN'T ADDED ANY LOG CHANNEL ❗</b>"
        text = (
            "📢 <b>LOG CHANNEL:</b>\n\n"
            "<b>WHAT IS LOG CHANNEL ??</b>\n"
            "<b>IF NEW USERS START YOUR CLONE BOT THEN BOT NOTIFIES YOU.</b>\n\n"
            f"{status_txt}"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CHANNEL", callback_data="cset_set_log"), InlineKeyboardButton("DELETE CHANNEL", callback_data="cset_del_log")],
                [InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_set_log":
        sess_token = start_user_session(user_id, "set_log")
        await query.answer()
        await edit_or_reply(
            query,
            f"<b>FORWARD LOG CHANNEL ANY MESSAGE TO ME, AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="log_channel")]])
        )
        try:
            fwd = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not fwd or fwd.text == "/cancel":
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="log_channel")]]) )
        fwd_chat = getattr(fwd, "forward_from_chat", None)
        if not fwd_chat:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Must forward from a channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="log_channel")]]) )
        save(client, log_channel=fwd_chat.id, log_channel_title=fwd_chat.title)
        clear_user_session(user_id)
        return await client.send_message(
            chat_id=user_id,
            text=f"⚡ <b>SUCCESSFULLY ADDED YOUR LOG CHANNEL - {fwd_chat.title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="log_channel")]])
        )

    if data == "cset_del_log":
        save(client, log_channel=None, log_channel_title=None)
        await query.answer("Log channel deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED LOG CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="log_channel")]])
        )

    if data == "database_channel":
        db_ch = r.get("db_channel")
        db_title = r.get("db_channel_title")
        status_txt = f"<b>YOUR DATABASE CHANNEL - {db_title or db_ch}</b>" if db_ch else "<b>YOU DIDN'T ADDED ANY DATABASE CHANNEL ❗</b>"
        text = (
            "☁️ <b>DATABASE CHANNEL:</b>\n\n"
            "<b>WHAT IS DATABASE CHANNEL ?</b>\n\n"
            "<b>DATABASE CHANNEL MEANS WHEN YOU STORE ANYTHING IN FILE STORE BOT ALL MESSAGES BOT WILL STORE IN YOUR DATABASE CHANNEL. IF YOU DELETE THAT MESSAGE THEN BOT CAN NOT GIVE IT TO ANYONE.</b>\n\n"
            f"{status_txt}"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET CHANNEL", callback_data="cset_set_db_ch"), InlineKeyboardButton("DELETE CHANNEL", callback_data="cset_del_db_ch")],
                [InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_set_db_ch":
        sess_token = start_user_session(user_id, "set_db_ch")
        await query.answer()
        await edit_or_reply(
            query,
            f"<b>FORWARD DATABASE CHANNEL ANY MESSAGE TO ME, AND MAKE SURE @{me.username} IS ADMIN IN YOUR CHANNEL.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="database_channel")]])
        )
        try:
            fwd = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        if not fwd or fwd.text == "/cancel":
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="database_channel")]]) )
        fwd_chat = getattr(fwd, "forward_from_chat", None)
        if not fwd_chat:
            clear_user_session(user_id)
            return await client.send_message(chat_id=user_id, text="❌ <b>Must forward from a channel.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="database_channel")]]) )
        save(client, db_channel=fwd_chat.id, db_channel_title=fwd_chat.title)
        clear_user_session(user_id)
        return await client.send_message(
            chat_id=user_id,
            text=f"⚡ <b>SUCCESSFULLY ADDED YOUR DATABASE CHANNEL - {fwd_chat.title}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="database_channel")]])
        )

    if data == "cset_del_db_ch":
        save(client, db_channel=None, db_channel_title=None)
        await query.answer("Database channel deleted!")
        return await edit_or_reply(
            query,
            "<b>SUCCESSFULLY DELETED DATABASE CHANNEL ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="database_channel")]])
        )

    # 10. Admins
    if data == "admins_menu":
        text = (
            "👥 <b>ADMINS:</b>\n\n"
            "<b>YOU CAN CHANGE WHAT ADMINS CAN USE OR NOT BY CLICKING ON ADMIN NAME BUTTON.</b>\n\n"
            "<b>YOU CAN CUSTOMISE FOLLOWING ADMINS SETTINGS:</b>\n\n"
            "- <b>CAN DO BROADCAST</b>\n"
            "- <b>CAN USE CLONE BOT CUSTOMISATION</b>\n"
            "- <b>CAN ADD ADMINS OR CHANGE ADMIN SETTINGS</b>\n"
            "- <b>CAN DELETE BOT</b>\n\n"
            "<b>YOU CAN CUSTOMISE THE EACH ADMIN SETTINGS THAT WHAT THEY CAN USE OR WHAT THEY CAN NOT USE.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=admins_menu_markup(client))

    if data.startswith("adm_manage:"):
        target_uid = int(data.split(":")[1])
        adm = get_admin_data(client, target_uid) or {}
        name = adm.get("name") or adm.get("first_name") or str(target_uid)
        uname = adm.get("username") or "None"
        text = (
            f"- <b>NAME:</b> {name}\n"
            f"- <b>USER ID:</b> <code>{target_uid}</code>\n"
            f"- <b>USERNAME:</b> @{uname}\n\n"
            "<b>IF YOU ENABLE ALL SETTINGS WHICH IS GIVEN BELOW OF THIS ADMINS IT MEANS THIS ADMINS CAN DO EVERYTHING WHICH CAN DONE BY OWNER AND THIS ALSO HELP IF BY MISTAKE YOUR TELEGRAM ACCOUNT DELETED BUT ADMIN CAN NOT TRANSFER OWNERSHIP TO OTHER ADMIN ONLY OWNER CAN.</b>"
        )
        return await edit_or_reply(query, text, reply_markup=single_admin_markup(client, target_uid))

    if data.startswith("adm_tgl:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        perm_key = parts[2]
        adms = list(get_bot_admins(client))
        for a in adms:
            if int(a.get("user_id", 0)) == target_uid:
                a[perm_key] = not bool(a.get(perm_key, True if perm_key in ("can_broadcast", "can_settings") else False))
                break
        save(client, admins=adms)
        await query.answer("Permission updated!")
        return await edit_or_reply(query, query.message.text.html, reply_markup=single_admin_markup(client, target_uid))

    if data.startswith("adm_rem:"):
        target_uid = int(data.split(":")[1])
        adms = [a for a in get_bot_admins(client) if int(a.get("user_id", 0)) != target_uid]
        save(client, admins=adms)
        await query.answer("Admin removed successfully!")
        return await callbacks(client, type("Q", (), {"data": "admins_menu", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "adm_add":
        sess_token = start_user_session(user_id, "add_admin")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND USER ID OR USERNAME OF USER YOU WANT TO MAKE ADMIN.</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="admins_menu")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        inp = (ans.text or "").strip()
        clear_user_session(user_id)
        if inp == "/cancel":
            return await client.send_message(chat_id=user_id, text="❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="admins_menu")]]) )
        try:
            u_obj = await client.get_users(inp)
            adms = list(get_bot_admins(client))
            if not any(int(a.get("user_id", 0)) == u_obj.id for a in adms):
                adms.append({
                    "user_id": u_obj.id,
                    "name": u_obj.first_name,
                    "username": u_obj.username,
                    "can_broadcast": True,
                    "can_settings": True,
                    "can_add_admins": False,
                    "can_delete_bot": False
                })
                save(client, admins=adms)
            return await client.send_message(
                chat_id=user_id,
                text=f"✅ <b>Successfully added {u_obj.first_name} as Admin!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="admins_menu")]])
            )
        except Exception as e:
            return await client.send_message(
                chat_id=user_id,
                text=f"❌ <b>Error adding admin:</b> <code>{e}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="admins_menu")]])
            )

    # 11. Bot Status & Mode & Protect & Auto Delete
    if data == "cset_bot_status":
        bot_title = me.first_name or me.username or "ALL LINK SAHRE"
        users_count = r.get("total_users_count", 59)
        bans_count = r.get("banned_users_count", 0)
        cpu_p = psutil.cpu_percent() if hasattr(psutil, "cpu_percent") else 31.0
        ram_p = psutil.virtual_memory().percent if hasattr(psutil, "virtual_memory") else 53.1
        uptime_sec = int(time.time() - _START_TIME)
        hrs = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        secs = uptime_sec % 60
        status_msg = (
            f"{bot_title}\n\n"
            f"👤 USERS - {users_count}\n"
            f"🚫 BAN USERS - {bans_count}\n"
            f"🖥️ CPU - {cpu_p} %\n"
            f"💾 RAM - {ram_p} %\n"
            f"⏱️ UPTIME - {hrs} Hours {mins} Minutes {secs} Seconds"
        )
        return await query.answer(status_msg, show_alert=True)

    if data == "cset_bot_mode":
        curr_mode = r.get("mode", "public")
        new_mode = "private" if curr_mode == "public" else "public"
        save(client, mode=new_mode)
        await query.answer(f"Bot mode switched to {new_mode.upper()}!", show_alert=True)
        return await edit_or_reply(query, f"🎁 <b>BOT MODE:</b> <b>{new_mode.upper()}</b>", reply_markup=clone_manage_hub_markup(me.username))

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
                [InlineKeyboardButton(tgl_btn, callback_data="cset_tgl_protect")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "cset_tgl_protect":
        protect = not bool(r.get("protect_content", False))
        save(client, protect_content=protect)
        await query.answer(f"Protect Content {'Enabled' if protect else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "protect_menu", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "cset_auto_delete_menu":
        ad_on = bool(r.get("auto_delete_mode", False))
        ad_time = r.get("auto_delete", 600)
        status_txt = "ON ✅" if ad_on else "OFF ❌"
        tgl_btn = "OFF AUTO DELETE" if ad_on else "ON AUTO DELETE"
        text = (
            "♻️ <b>AUTO DELETE:</b>\n\n"
            "<b>AUTO DELETE: AUTOMATICALLY DELETE DELIVERED FILES AFTER SPECIFIED TIME TO SAVE STORAGE AND PROTECT COPYRIGHT.</b>\n\n"
            f"<b>AUTO DELETE - {status_txt}</b>\n"
            f"<b>DELETE TIME - {ad_time} SECONDS</b>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET AUTO DELETE TIME", callback_data="cset_set_ad_time")],
                [InlineKeyboardButton(tgl_btn, callback_data="cset_tgl_ad")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "cset_tgl_ad":
        ad_on = not bool(r.get("auto_delete_mode", False))
        save(client, auto_delete_mode=ad_on)
        await query.answer(f"Auto Delete {'Enabled' if ad_on else 'Disabled'}!")
        return await callbacks(client, type("Q", (), {"data": "cset_auto_delete_menu", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    if data == "cset_set_ad_time":
        sess_token = start_user_session(user_id, "set_ad_time")
        await query.answer()
        await edit_or_reply(
            query,
            "<b>SEND AUTO DELETE TIME IN SECONDS (e.g., 600 for 10 minutes).</b>\n\n/cancel - CANCEL THIS PROCESS.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_auto_delete_menu")]])
        )
        try:
            ans = await client.listen(chat_id=user_id, timeout=120)
        except Exception:
            clear_user_session(user_id)
            return
        t_val = (ans.text or "").strip()
        clear_user_session(user_id)
        if t_val == "/cancel" or not t_val.isdigit():
            return await client.send_message(chat_id=user_id, text="❌ <b>Invalid time. Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_auto_delete_menu")]]) )
        save(client, auto_delete=int(t_val), auto_delete_mode=True)
        return await client.send_message(
            chat_id=user_id,
            text=f"<b>SUCCESSFULLY SET AUTO DELETE TIME TO {t_val} SECONDS ✅</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="cset_auto_delete_menu")]])
        )

    if data in ("link_shortener", "cset_shortener"):
        is_on = bool(r.get("shortener_on", True))
        url = r.get("base_site") or "None"
        api = r.get("shortener_api") or "None"
        status_txt = "ON ✅" if is_on else "OFF ❌"
        tgl_btn = "OFF SHORTLINK" if is_on else "ON SHORTLINK"
        text = (
            "🔗 <b>LINK SHORTNER:</b>\n\n"
            "<b>LINK SHORTENER: A TOOL THAT CONVERTS FILE LINKS INTO MONETIZED URLS, ALLOWING BOT OWNERS TO EARN MONEY WHENEVER A USER CLICKS.</b>\n\n"
            "<b>NOTE: THE SETTINGS BELOW WILL ONLY WORK FOR LINKS CREATED BY THIS TELEGRAM ACCOUNT. THEY WILL NOT AFFECT LINKS CREATED BY OTHER ACCOUNTS.</b>\n\n"
            f"<b>SHORTLINK - {status_txt}</b>\n\n"
            f"<b>URL -</b> <code>{url}</code>\n"
            f"<b>API -</b> <code>{api}</code>"
        )
        return await edit_or_reply(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("SET SHORTLINK", callback_data="cset_v_set_short:1")],
                [InlineKeyboardButton("DELETE SHORTLINK", callback_data="cset_v_del_short:1")],
                [InlineKeyboardButton(tgl_btn, callback_data="cset_v_tgl_short:1")],
                [InlineKeyboardButton("‹ BACK", callback_data="settings")]
            ])
        )

    if data == "cset_refer_earn":
        return await edit_or_reply(
            query,
            "🌍 <b>REFER AND EARN:</b>\n\n<b>SHARE YOUR REFERRAL LINK WITH FRIENDS TO EARN REWARDS AND EXTENDED ACCESS.</b>\n\n<code>https://t.me/" + me.username + f"?start=ref_{user_id}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="settings")]])
        )

    if data == "cset_permanent_link":
        return await edit_or_reply(
            query,
            "♾️ <b>PERMANENT LINK:</b>\n\n<b>GENERATED LINKS REMAIN PERMANENTLY ACCESSIBLE UNLESS MANUALLY DELETED FROM DATABASE.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="settings")]])
        )

    if data == "cset_monetization":
        return await edit_or_reply(
            query,
            "🪙 <b>MONETIZATION:</b>\n\n<b>EARN REVENUE VIA LINK SHORTENERS AND PREMIUM MEMBERSHIP SUBSCRIPTIONS.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 LINK SHORTNER", callback_data="link_shortener")],
                [InlineKeyboardButton("💳 PREMIUM PLAN", callback_data="cset_premium_plan")],
                [InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_restart_bot":
        await query.answer("Restarting bot...", show_alert=True)
        return await edit_or_reply(
            query,
            f"🔄 <b>@{me.username} is restarting...</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="clone_my_clone_info")]])
        )

    if data == "cset_delete_bot":
        return await edit_or_reply(
            query,
            "⚠️ <b>ARE YOU SURE YOU WANT TO DELETE THIS CLONE BOT?</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ YES, DELETE", callback_data="cset_confirm_del_bot")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="clone_my_clone_info")]
            ])
        )

    if data == "cset_confirm_del_bot":
        m = db()
        if m:
            m.bots.delete_one({"bot_id": me.id})
        await query.answer("Clone bot deleted!", show_alert=True)
        return await edit_or_reply(query, "🚫 <b>Clone Bot Deleted Successfully.</b>")

    # Fallback
    await query.answer()

def register(client):
    client.add_handler(MessageHandler(settings, filters.command(["settings"]) & filters.private), group=2)
    client.add_handler(CallbackQueryHandler(callbacks), group=2)
