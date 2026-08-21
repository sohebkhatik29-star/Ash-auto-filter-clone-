# ASH FILE STORE & CLONE MANAGER - MASTER & CLONE BOTS MANAGER
import asyncio
import re
import random
from pyrogram import Client, filters
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session, cancel_all_listeners
from config import ADMINS, API_ID, API_HASH, PICS, BOT_USERNAME

MAX_USER_CLONES = 5

def db():
    from plugins.clone import mongo_db
    return mongo_db

def is_admin(uid):
    try:
        return int(uid) in {int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()}
    except Exception:
        return False

def docs_for(uid):
    m = db()
    if m is None:
        return []
    q = {} if is_admin(uid) else {"user_id": int(uid)}
    return list(m.bots.find(q, {"token": 0}).sort("bot_id", 1))

def owns(uid, bid):
    m = db()
    if not m:
        return False
    if is_admin(uid):
        return True
    return bool(m.bots.find_one({"bot_id": int(bid), "user_id": int(uid)}))

def get_bot(bid):
    m = db()
    return m.bots.find_one({"bot_id": int(bid)}) if m else None

def update_bot(bid, **values):
    m = db()
    if m:
        m.bots.update_one({"bot_id": int(bid)}, {"$set": values}, upsert=False)

def manage_clones_markup(uid, back_cb="start_back"):
    docs = docs_for(uid)
    rows = []
    for d in docs[:MAX_USER_CLONES]:
        bid = int(d["bot_id"])
        name = d.get("name") or d.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"🤖 @{name} ↗", callback_data=f"manage_clone:{bid}")])
    if len(docs) < MAX_USER_CLONES:
        rows.append([InlineKeyboardButton("➕ CREATE CLONE ➕", callback_data="create_clone_prompt")])
    else:
        rows.append([InlineKeyboardButton("🚫 BOT LIMIT 5/5", callback_data="clone_limit")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

def manage_markup(bid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("START MSG", callback_data=f"cm:{bid}:startmsg"), InlineKeyboardButton("FORCE SUB", callback_data=f"cm:{bid}:force")],
        [InlineKeyboardButton("MODERATORS", callback_data=f"cm:{bid}:mods"), InlineKeyboardButton("AUTO DELETE", callback_data=f"cm:{bid}:autodelete")],
        [InlineKeyboardButton("NO FORWARD", callback_data=f"cm:{bid}:noforward"), InlineKeyboardButton("ACCESS TOKEN", callback_data=f"cm:{bid}:access")],
        [InlineKeyboardButton("TRANSFER DB", callback_data=f"cm:{bid}:transfer"), InlineKeyboardButton("DEACTIVATE", callback_data=f"cm:{bid}:deactivate")],
        [InlineKeyboardButton("MODE", callback_data=f"cm:{bid}:mode"), InlineKeyboardButton("RESTART", callback_data=f"cm:{bid}:restart")],
        [InlineKeyboardButton("STATS", callback_data=f"cm:{bid}:stats"), InlineKeyboardButton("DELETE", callback_data=f"cm:{bid}:delete")],
        [InlineKeyboardButton("‹ BACK", callback_data="my_clones")]
    ])

def action_back(bid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]])

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

async def edit_setting(query, bid, title, value):
    await edit_or_reply(query, f"{title}\n\n{value}", reply_markup=action_back(bid))
    try:
        await query.answer()
    except Exception:
        pass

async def handle_clone_callbacks(client, query):
    data = query.data
    user_id = query.from_user.id
    m = db()

    if data in ("my_clone", "my_clones", "clone_my_bots"):
        text = (
            "✨ <b>HERE ARE YOUR ACTIVE BOTS WITH POWERFUL CLONING AND CUSTOMIZATION</b>\n\n"
            "📲 <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
        )
        is_clone = getattr(client, "is_bot", True) and client.me.username != BOT_USERNAME
        back_cb = "start_back" if is_clone else "settings_back"
        return await edit_or_reply(query, text, reply_markup=manage_clones_markup(user_id, back_cb=back_cb))

    if data == "clone_limit":
        return await query.answer("❌ You can create maximum 5 clone bots.", show_alert=True)

    if data == "create_clone_prompt":
        if m is not None:
            current_count = m.bots.count_documents({"user_id": int(user_id)})
            if current_count >= MAX_USER_CLONES:
                return await query.answer("❌ You can create maximum 5 clone bots.", show_alert=True)
        try:
            await query.answer()
        except Exception:
            pass
        cancel_all_listeners(client, query.message.chat.id, user_id)
        sess_token = start_user_session(user_id, "create_clone")
        prompt_text = (
            "🤖 <b>CREATE CLONE BOT:</b>\n\n"
            "1) Create a bot using @BotFather\n"
            "2) Then you will get a message with bot token\n"
            "3) Send that bot token here\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        await client.send_message(
            chat_id=user_id,
            text=prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data="my_clones")]])
        )
        asyncio.create_task(_listen_and_create_clone(client, user_id, sess_token))
        return

    if data.startswith("manage_clone:"):
        bid = int(data.split(":")[1])
        if not owns(user_id, bid):
            return await query.answer("❌ You can manage only your own clones.", show_alert=True)
        d = get_bot(bid) or {}
        title = d.get("name") or d.get("username") or str(bid)
        uname = d.get("username", "")
        uname_text = f"\n➣ <b>Username:</b> @{uname}" if uname else ""
        text = (
            "🪄 <u><b>Customize Clone</b></u>\n\n"
            f"➣ <b>Name:</b> <code>{title}</code>"
            f"{uname_text}\n\n"
            "<b>Configure Your Clone Settings Using Given Buttons</b>"
        )
        await edit_or_reply(query, text, reply_markup=manage_markup(bid))
        try:
            await query.answer()
        except Exception:
            pass
        return

    if data.startswith("cm:"):
        _, raw, action = data.split(":")
        bid = int(raw)
        if not owns(user_id, bid):
            return await query.answer("❌ Access denied.", show_alert=True)
        d = get_bot(bid) or {}

        if action == "deactivate":
            state = not bool(d.get("deactivated", False))
            update_bot(bid, deactivated=state)
            return await edit_setting(query, bid, "⏸ <b>DEACTIVATE</b>", f"Status: <b>{DEACTIVATED if state else ACTIVE}</b>")

        if action == "noforward":
            state = not bool(d.get("no_forward", False))
            update_bot(bid, no_forward=state)
            return await edit_setting(query, bid, "🚫 <b>NO FORWARD</b>", f"Status: <b>{ON if state else OFF}</b>")

        if action == "protect":
            state = not bool(d.get("protect_content", False))
            update_bot(bid, protect_content=state)
            return await edit_setting(query, bid, "🛡️ <b>PROTECT CONTENT</b>", f"Status: <b>{ON if state else OFF}</b>")

        if action == "access":
            state = not bool(d.get("access_token_enabled", True))
            update_bot(bid, access_token_enabled=state)
            return await edit_setting(query, bid, "🔑 <b>ACCESS TOKEN</b>", f"Status: <b>{ON if state else OFF}</b>\nValidity: {d.get(access_token_hours, 1)} hour(s)")

        if action == "mode":
            new_mode = "public" if d.get("mode", "private") == "private" else "private"
            update_bot(bid, mode=new_mode)
            return await edit_setting(query, bid, "🔒 <b>MODE</b>", f"Current mode: <b>{new_mode.upper()}</b>")

        if action == "restart":
            update_bot(bid, restart_requested=True)
            return await edit_setting(query, bid, "🔄 <b>RESTART</b>", "Restart request saved. The clone will reload on next startup.")

        if action == "stats":
            from clone_plugins.dbusers import clonedb
            try:
                users_cnt = await clonedb.total_users_count(bid)
            except Exception:
                users_cnt = d.get("user_count", 0)
            return await edit_setting(query, bid, "📊 <b>CLONE STATS</b>", f"Bot ID: <code>{bid}</code>\nUsers: <code>{users_cnt}</code>")

        if action == "delete":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ YES, DELETE", callback_data=f"cmdelete:{bid}"), InlineKeyboardButton("CANCEL", callback_data=f"manage_clone:{bid}")]
            ])
            await edit_or_reply(query, "⚠️ <b>Delete this clone record?</b>\n\nThis removes the clone from the database.", reply_markup=kb)
            try:
                await query.answer()
            except Exception:
                pass
            return

        if action == "autodelete":
            state = not bool(d.get("auto_delete_enabled", False))
            minutes = int(d.get("auto_delete_minutes", 15) or 15)
            update_bot(bid, auto_delete_enabled=state, auto_delete_minutes=minutes)
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("➖ 1 MIN", callback_data=f"cad:{bid}:minus"), InlineKeyboardButton(f"⏱ {minutes} MIN", callback_data=f"cad:{bid}:noop"), InlineKeyboardButton("➕ 1 MIN", callback_data=f"cad:{bid}:plus")],
                [InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]
            ])
            await edit_or_reply(query, f"🗑️ <b>AUTO DELETE</b>\n\nStatus: <b>{ON if state else OFF}</b>\nTime: <code>{minutes}</code> minutes", reply_markup=buttons)
            try:
                await query.answer()
            except Exception:
                pass
            return

        if action == "force":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_force_{bid}")
            await client.send_message(user_id, "📢 Send channel username/ID to add. Send <code>off</code> to clear Force Subscribe.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_force(client, user_id, bid, sess))
            return

        if action == "mods":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_mods_{bid}")
            mods = [int(x) for x in d.get("moderators", []) if str(x).isdigit()]
            cur_mods = "\n".join(f"• <code>{x}</code>" for x in mods) or "None"
            await client.send_message(user_id, f"👮 <b>MODERATORS</b>\n\nCurrent moderators:\n{cur_mods}\n\nSend <code>add USER_ID</code>, <code>del USER_ID</code>, or <code>list</code>.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_mods(client, user_id, bid, sess))
            return

        if action == "startmsg":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_startmsg_{bid}")
            await client.send_message(user_id, "📝 Send the new start message. Send <code>off</code> to remove custom message.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_startmsg(client, user_id, bid, sess))
            return

        if action == "caption":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_caption_{bid}")
            await client.send_message(user_id, "📝 Send custom caption. Send <code>off</code> to disable.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_caption(client, user_id, bid, sess))
            return

        if action == "button":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_button_{bid}")
            await client.send_message(user_id, "➕ Send <code>Button Text - https://example.com</code>. Send <code>off</code> to clear buttons.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_button(client, user_id, bid, sess))
            return

        if action == "shortener":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_shortener_{bid}")
            await client.send_message(user_id, "🔗 Send <code>API_KEY | BASE_SITE</code>. Send <code>off</code> to disable.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_shortener(client, user_id, bid, sess))
            return

        if action == "startpic":
            try:
                await query.answer()
            except Exception:
                pass
            cancel_all_listeners(client, query.message.chat.id, user_id)
            sess = start_user_session(user_id, f"cm_startpic_{bid}")
            await client.send_message(user_id, "🖼️ Send image URL for the clone start photo. Send <code>off</code> to reset.", reply_markup=action_back(bid))
            asyncio.create_task(_listen_startpic(client, user_id, bid, sess))
            return

        if action == "transfer":
            return await edit_setting(query, bid, "🔄 <b>TRANSFER DB</b>", "Ownership transfer requires contacting support or using admin commands.")

    if data.startswith("cad:"):
        _, raw, op = data.split(":")
        bid = int(raw)
        if not owns(user_id, bid):
            return await query.answer("❌ Access denied.", show_alert=True)
        d = get_bot(bid) or {}
        minutes = max(1, min(1440, int(d.get("auto_delete_minutes", 15) or 15)))
        if op == "minus":
            minutes = max(1, minutes - 1)
        elif op == "plus":
            minutes = min(1440, minutes + 1)
        update_bot(bid, auto_delete_minutes=minutes)
        state = bool(d.get("auto_delete_enabled", False))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➖ 1 MIN", callback_data=f"cad:{bid}:minus"), InlineKeyboardButton(f"⏱ {minutes} MIN", callback_data=f"cad:{bid}:noop"), InlineKeyboardButton("➕ 1 MIN", callback_data=f"cad:{bid}:plus")],
            [InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]
        ])
        await edit_or_reply(query, f"🗑️ <b>AUTO DELETE</b>\n\nStatus: <b>{ON if state else OFF}</b>\nTime: <code>{minutes}</code> minutes", reply_markup=kb)
        try:
            await query.answer()
        except Exception:
            pass
        return

    if data.startswith("cmdelete:"):
        bid = int(data.split(":")[1])
        if not owns(user_id, bid):
            return await query.answer("❌ Access denied.", show_alert=True)
        if m:
            m.bots.delete_one({"bot_id": bid, "user_id": int(user_id)} if not is_admin(user_id) else {"bot_id": bid})
        await edit_or_reply(query, "🗑️ <b>Clone removed from the database.</b>", reply_markup=manage_clones_markup(user_id))
        try:
            await query.answer("Deleted")
        except Exception:
            pass
        return

async def _listen_and_create_clone(client, user_id, sess_token):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess_token):
        return
    clear_user_session(user_id)
    txt = (ans.text or "").strip()
    if txt.lower() == "/cancel":
        return await client.send_message(user_id, "<b>Cancelled 🚫</b>")
    match = re.search(r"\b(\d+:[A-Za-z0-9_-]+)\b", txt)
    if not match:
        return await client.send_message(user_id, "<b>❌ Could not read the bot token. Please send a valid token.</b>")
    bot_token = match.group(1)

    m = db()
    if m is not None:
        current_count = m.bots.count_documents({"user_id": int(user_id)})
        if current_count >= MAX_USER_CLONES:
            return await client.send_message(user_id, "❌ <b>You can create maximum 5 clone bots.</b>")

    msg = await client.send_message(user_id, "<b>👨‍💻 Creating your clone...</b>")
    try:
        from plugins.clone import register_clone_handlers, set_clone_menu
        bot_prefix = int(bot_token.split(":")[0])
        vj = Client(f"clone_{user_id}_{bot_prefix}", API_ID, API_HASH, bot_token=bot_token, plugins={})
        await vj.start()
        register_clone_handlers(vj)
        bot = await vj.get_me()
        if m is not None:
            m.bots.update_one(
                {"bot_id": bot.id},
                {"$set": {
                    "bot_id": bot.id,
                    "is_bot": True,
                    "user_id": int(user_id),
                    "name": bot.first_name,
                    "token": bot_token,
                    "username": bot.username,
                    "force_channels": [],
                    "custom_caption": None,
                    "custom_buttons": [],
                    "protect_content": False,
                    "no_forward": False,
                    "auto_delete_enabled": False,
                    "auto_delete_minutes": 15,
                    "access_token_enabled": False,
                    "access_token_hours": 1,
                    "moderators": [],
                    "mode": "private",
                    "deactivated": False,
                    "hide_owner": False
                }},
                upsert=True
            )
        await set_clone_menu(vj, int(user_id))
        await msg.edit_text(
            f"✨ <b>Successfully Cloned Your Bot: @{bot.username}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🤖 OPEN @{bot.username} ↗", url=f"https://t.me/{bot.username}")],
                [InlineKeyboardButton("‹ MY CLONE BOTS", callback_data="my_clones")]
            ])
        )
    except Exception as e:
        await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>")

async def _listen_force(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    val = (ans.text or "").strip()
    d = get_bot(bid) or {}
    if val.lower() == "off":
        update_bot(bid, force_channels=[])
        return await client.send_message(user_id, "📢 <b>FORCE SUB</b>\n\nDisabled.", reply_markup=action_back(bid))
    try:
        chat = await client.get_chat(val)
        channels = list(d.get("force_channels", []))
        if chat.id not in channels:
            channels.append(chat.id)
        update_bot(bid, force_channels=channels)
        return await client.send_message(user_id, f"📢 <b>FORCE SUB</b>\n\nAdded: <code>{chat.id}</code>\n\nMake the clone bot admin in that channel.", reply_markup=action_back(bid))
    except Exception:
        return await client.send_message(user_id, "❌ Could not access that channel. Check username/ID and admin permissions.", reply_markup=action_back(bid))

async def _listen_mods(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    parts = (ans.text or "").split()
    d = get_bot(bid) or {}
    mods = [int(x) for x in d.get("moderators", []) if str(x).isdigit()]
    if not parts or parts[0].lower() == "list":
        text = "\n".join(f"• <code>{x}</code>" for x in mods) or "No moderators."
    elif len(parts) == 2 and parts[1].isdigit() and parts[0].lower() in ("add", "del"):
        uid = int(parts[1])
        if parts[0].lower() == "add" and uid not in mods:
            mods.append(uid)
        if parts[0].lower() == "del":
            mods = [x for x in mods if x != uid]
        update_bot(bid, moderators=mods)
        text = "✅ Moderator list updated.\n\n" + ("\n".join(f"• <code>{x}</code>" for x in mods) or "No moderators.")
    else:
        text = "❌ Format: <code>add USER_ID</code> or <code>del USER_ID</code>"
    return await client.send_message(user_id, "👮 <b>MODERATORS</b>\n\n" + text, reply_markup=action_back(bid))

async def _listen_startmsg(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    text = (ans.text or "").strip()
    update_bot(bid, start_message=None if text.lower() == "off" else text[:4000])
    return await client.send_message(user_id, "📝 <b>START MESSAGE</b>\n\n" + ("Disabled." if text.lower() == "off" else "Saved successfully."), reply_markup=action_back(bid))

async def _listen_caption(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    text = (ans.text or "").strip()
    update_bot(bid, custom_caption=None if text.lower() == "off" else text[:4000])
    return await client.send_message(user_id, "📝 <b>CUSTOM CAPTION</b>\n\n" + ("Disabled." if text.lower() == "off" else "Saved successfully."), reply_markup=action_back(bid))

async def _listen_button(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    text = (ans.text or "").strip()
    if text.lower() == "off":
        update_bot(bid, custom_buttons=[])
        return await client.send_message(user_id, "➕ <b>CUSTOM BUTTON</b>\n\nButtons cleared.", reply_markup=action_back(bid))
    if " - " not in text:
        return await client.send_message(user_id, "❌ Format: <code>Button Text - https://example.com</code>", reply_markup=action_back(bid))
    label, url = [x.strip() for x in text.split(" - ", 1)]
    if not url.startswith(("http://", "https://")):
        return await client.send_message(user_id, "❌ URL must start with http:// or https://", reply_markup=action_back(bid))
    d = get_bot(bid) or {}
    buttons = list(d.get("custom_buttons", []))
    buttons.append({"text": label[:64], "url": url})
    update_bot(bid, custom_buttons=buttons)
    return await client.send_message(user_id, "➕ <b>CUSTOM BUTTON</b>\n\nButton added successfully.", reply_markup=action_back(bid))

async def _listen_shortener(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    text = (ans.text or "").strip()
    if text.lower() == "off":
        update_bot(bid, shortener_api=None, base_site=None)
        return await client.send_message(user_id, "🔗 <b>LINK SHORTENER</b>\n\nDisabled.", reply_markup=action_back(bid))
    if "|" not in text:
        return await client.send_message(user_id, "❌ Format: <code>API_KEY | vplink.in</code>", reply_markup=action_back(bid))
    api, site = [x.strip() for x in text.split("|", 1)]
    site = site.replace("https://", "").replace("http://", "").rstrip("/")
    update_bot(bid, shortener_api=api, base_site=site)
    return await client.send_message(user_id, "🔗 <b>LINK SHORTENER</b>\n\nAPI and base site saved for this clone.", reply_markup=action_back(bid))

async def _listen_startpic(client, user_id, bid, sess):
    try:
        ans = await client.listen(chat_id=user_id, timeout=120)
    except Exception:
        clear_user_session(user_id)
        return
    if not is_user_session_active(user_id, sess):
        return
    clear_user_session(user_id)
    text = (ans.text or "").strip()
    if text.lower() == "off":
        update_bot(bid, start_pic=None)
        return await client.send_message(user_id, "🖼️ <b>START PHOTO</b>\n\nReset to default photo.", reply_markup=action_back(bid))
    if not text.startswith(("http://", "https://")):
        return await client.send_message(user_id, "❌ URL must start with http:// or https://", reply_markup=action_back(bid))
    update_bot(bid, start_pic=text)
    return await client.send_message(user_id, "🖼️ <b>START PHOTO</b>\n\nCustom start photo updated successfully.", reply_markup=action_back(bid))

CLONE_CALLBACK_REGEX = r"^(my_clone|my_clones|clone_my_bots|create_clone_prompt|clone_limit|manage_clone:\d+|cm:\d+:[a-z_]+|cad:\d+:[a-z_]+|cmdelete:\d+)$"

def register(client):
    client.add_handler(CallbackQueryHandler(handle_clone_callbacks, filters.regex(CLONE_CALLBACK_REGEX)), group=1)
