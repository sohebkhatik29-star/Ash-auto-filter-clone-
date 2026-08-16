"""Master-bot clone management UI.

This module deliberately imports the clone database lazily.  plugins.clone imports
this module while it is being loaded, so importing mongo_db at module import time
would create a circular-import failure and silently disable all manager callbacks.
"""
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from config import ADMINS


def db():
    from plugins.clone import mongo_db
    return mongo_db


def is_admin(uid):
    try:
        return int(uid) in {int(x) for x in ADMINS}
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
    return bool(m and (is_admin(uid) or m.bots.find_one({"bot_id": int(bid), "user_id": int(uid)})))


def get_bot(bid):
    m = db()
    return m.bots.find_one({"bot_id": int(bid)}) if m else None


def update_bot(bid, **values):
    m = db()
    if m:
        m.bots.update_one({"bot_id": int(bid)}, {"$set": values}, upsert=False)


def list_markup(docs):
    rows = []
    for d in docs:
        bid = int(d["bot_id"])
        name = d.get("name") or d.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"🤖 {name[:32]}", callback_data=f"manage_clone:{bid}")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def manage_markup(bid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("START MSG", callback_data=f"cm:{bid}:startmsg"), InlineKeyboardButton("FORCE SUB", callback_data=f"cm:{bid}:force")],
        [InlineKeyboardButton("MODERATORS", callback_data=f"cm:{bid}:mods"), InlineKeyboardButton("AUTO DELETE", callback_data=f"cm:{bid}:autodelete")],
        [InlineKeyboardButton("NO FORWARD", callback_data=f"cm:{bid}:noforward"), InlineKeyboardButton("ACCESS TOKEN", callback_data=f"cm:{bid}:access")],
        [InlineKeyboardButton("TRANSFER DB", callback_data=f"cm:{bid}:transfer"), InlineKeyboardButton("DEACTIVATE", callback_data=f"cm:{bid}:deactivate")],
        [InlineKeyboardButton("MODE", callback_data=f"cm:{bid}:mode"), InlineKeyboardButton("RESTART", callback_data=f"cm:{bid}:restart")],
        [InlineKeyboardButton("STATS", callback_data=f"cm:{bid}:stats"), InlineKeyboardButton("DELETE", callback_data=f"cm:{bid}:delete")],
        [InlineKeyboardButton("BACK", callback_data="my_clones")]
    ])


def action_back(bid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]])


async def edit_setting(query, bid, title, value):
    await query.message.edit_text(f"{title}\n\n{value}", reply_markup=action_back(bid))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^my_clones$"))
async def my_clones(client, query):
    from plugins.master_settings import manage_clones_markup
    text = (
        "✨ <b>Manage Clone's</b>\n\n"
        "You can now manage and create your very own identical clone bot, "
        "mirroring all my awesome features, using the given buttons."
    )
    await query.message.edit_text(text, reply_markup=manage_clones_markup(query.from_user.id))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^manage_clone:\d+$"))
async def manage_clone(client, query):
    bid = int(query.data.split(":")[1])
    if not owns(query.from_user.id, bid):
        return await query.answer("❌ You can manage only your own clones.", show_alert=True)
    d = get_bot(bid) or {}
    title = d.get("name") or d.get("username") or str(bid)
    text = (
        "🪄 <u><b>Customize Clone</b></u>\n\n"
        f"➣ <b>Name:</b> <code>{title}</code>\n\n"
        "<b>Configure Your Clone Settings Using Given Buttons</b>"
    )
    await query.message.edit_text(text, reply_markup=manage_markup(bid))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^cm:\d+:(startmsg|force|mods|autodelete|noforward|access|transfer|deactivate|mode|restart|stats|delete|shortener|caption|button|startpic|protect)$"))
async def clone_manage_action(client, query):
    _, raw, action = query.data.split(":")
    bid = int(raw)
    if not owns(query.from_user.id, bid):
        return await query.answer("❌ Access denied.", show_alert=True)
    d = get_bot(bid) or {}

    if action == "deactivate":
        state = not bool(d.get("deactivated", False))
        update_bot(bid, deactivated=state)
        return await edit_setting(query, bid, "⏸ <b>DEACTIVATE</b>", f"Status: <b>{'DEACTIVATED' if state else 'ACTIVE'}</b>")

    if action == "noforward":
        state = not bool(d.get("no_forward", False))
        update_bot(bid, no_forward=state)
        return await edit_setting(query, bid, "🚫 <b>NO FORWARD</b>", f"Status: <b>{'ON' if state else 'OFF'}</b>")

    if action == "protect":
        state = not bool(d.get("protect_content", False))
        update_bot(bid, protect_content=state)
        return await edit_setting(query, bid, "🛡️ <b>PROTECT CONTENT</b>", f"Status: <b>{'ON' if state else 'OFF'}</b>")

    if action == "autodelete":
        state = not bool(d.get("auto_delete_enabled", False))
        minutes = int(d.get("auto_delete_minutes", 15) or 15)
        update_bot(bid, auto_delete_enabled=state, auto_delete_minutes=minutes)
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("➖ 1 MIN", callback_data=f"cad:{bid}:minus"), InlineKeyboardButton(f"⏱ {minutes} MIN", callback_data=f"cad:{bid}:noop"), InlineKeyboardButton("➕ 1 MIN", callback_data=f"cad:{bid}:plus")], [InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]])
        await query.message.edit_text(f"🗑️ <b>AUTO DELETE</b>\n\nStatus: <b>{'ON' if state else 'OFF'}</b>\nTime: <code>{minutes}</code> minutes", reply_markup=buttons)
        return await query.answer()

    if action == "access":
        state = not bool(d.get("access_token_enabled", True))
        update_bot(bid, access_token_enabled=state)
        return await edit_setting(query, bid, "🔑 <b>ACCESS TOKEN</b>", f"Status: <b>{'ON' if state else 'OFF'}</b>\nValidity: {d.get('access_token_hours', 1)} hour(s)")

    if action == "mode":
        new_mode = "public" if d.get("mode", "private") == "private" else "private"
        update_bot(bid, mode=new_mode)
        return await edit_setting(query, bid, "🔒 <b>MODE</b>", f"Current mode: <b>{new_mode}</b>")

    if action == "restart":
        update_bot(bid, restart_requested=True)
        return await edit_setting(query, bid, "🔄 <b>RESTART</b>", "Restart request saved. The clone will reload on the next service restart.")

    if action == "stats":
        try:
            users = await clonedb.total_users_count(bid)
        except Exception:
            users = d.get("user_count", 0)
        return await edit_setting(query, bid, "📊 <b>CLONE STATS</b>", f"Bot ID: <code>{bid}</code>\nUsers: <code>{users}</code>")

    if action == "delete":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ YES, DELETE", callback_data=f"cmdelete:{bid}"), InlineKeyboardButton("CANCEL", callback_data=f"manage_clone:{bid}")]])
        await query.message.edit_text("⚠️ <b>Delete this clone record?</b>\n\nThis removes the clone from the manager database.", reply_markup=kb)
        return await query.answer()

    if action == "force":
        await query.answer()
        try:
            ans = await client.ask(query.from_user.id, "📢 Send channel username/ID to add. Send <code>off</code> to clear Force Subscribe.", timeout=120)
            val = (ans.text or "").strip()
            if val.lower() == "off":
                update_bot(bid, force_channels=[])
                return await query.message.edit_text("📢 <b>FORCE SUB</b>\n\nDisabled.", reply_markup=action_back(bid))
            try:
                chat = await client.get_chat(val)
                channels = list(d.get("force_channels", []))
                if chat.id not in channels: channels.append(chat.id)
                update_bot(bid, force_channels=channels)
                return await query.message.edit_text(f"📢 <b>FORCE SUB</b>\n\nAdded: <code>{chat.id}</code>\n\nMake the clone bot admin in that channel.", reply_markup=action_back(bid))
            except Exception:
                return await query.message.edit_text("❌ Could not access that channel. Check the username/ID and bot permissions.", reply_markup=action_back(bid))
        except Exception:
            return await query.message.edit_text("⌛ Request timed out.", reply_markup=action_back(bid))

    if action == "mods":
        await query.answer()
        ans = await client.ask(query.from_user.id, "👮 Send <code>add USER_ID</code>, <code>del USER_ID</code>, or <code>list</code>.", timeout=120)
        parts = (ans.text or "").split()
        mods = [int(x) for x in d.get("moderators", []) if str(x).isdigit()]
        if not parts or parts[0].lower() == "list":
            text = "\n".join(f"• <code>{x}</code>" for x in mods) or "No moderators."
        elif len(parts) == 2 and parts[1].isdigit() and parts[0].lower() in ("add", "del"):
            uid = int(parts[1])
            if parts[0].lower() == "add" and uid not in mods: mods.append(uid)
            if parts[0].lower() == "del": mods = [x for x in mods if x != uid]
            update_bot(bid, moderators=mods)
            text = "✅ Moderator list updated.\n\n" + ("\n".join(f"• <code>{x}</code>" for x in mods) or "No moderators.")
        else:
            text = "❌ Format: <code>add USER_ID</code> or <code>del USER_ID</code>"
        return await query.message.edit_text("👮 <b>MODERATORS</b>\n\n" + text, reply_markup=action_back(bid))

    if action == "startmsg":
        await query.answer()
        ans = await client.ask(query.from_user.id, "📝 Send the new start message. Send <code>off</code> to remove it.", timeout=120)
        text = (ans.text or "").strip()
        update_bot(bid, start_message=None if text.lower() == "off" else text[:4000])
        return await query.message.edit_text("📝 <b>START MESSAGE</b>\n\n" + ("Disabled." if text.lower() == "off" else "Saved successfully."), reply_markup=action_back(bid))

    if action == "caption":
        await query.answer()
        ans = await client.ask(query.from_user.id, "📝 Send custom caption. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        update_bot(bid, custom_caption=None if text.lower() == "off" else text[:4000])
        return await query.message.edit_text("📝 <b>CUSTOM CAPTION</b>\n\nSaved successfully.", reply_markup=action_back(bid))

    if action == "button":
        await query.answer()
        ans = await client.ask(query.from_user.id, "➕ Send <code>Button Text - https://example.com</code>. Send <code>off</code> to clear.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            update_bot(bid, custom_buttons=[])
            return await query.message.edit_text("➕ <b>CUSTOM BUTTON</b>\n\nButtons cleared.", reply_markup=action_back(bid))
        if " - " not in text:
            return await query.message.edit_text("❌ Format: <code>Button Text - https://example.com</code>", reply_markup=action_back(bid))
        label, url = [x.strip() for x in text.split(" - ", 1)]
        if not url.startswith(("http://", "https://")):
            return await query.message.edit_text("❌ URL must start with http:// or https://", reply_markup=action_back(bid))
        buttons = list(d.get("custom_buttons", []))
        buttons.append({"text": label[:64], "url": url})
        update_bot(bid, custom_buttons=buttons)
        return await query.message.edit_text("➕ <b>CUSTOM BUTTON</b>\n\nButton added successfully.", reply_markup=action_back(bid))

    if action == "shortener":
        await query.answer()
        ans = await client.ask(query.from_user.id, "🔗 Send <code>API_KEY | BASE_SITE</code>. Send <code>off</code> to disable.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            update_bot(bid, shortener_api=None, base_site=None)
            return await query.message.edit_text("🔗 <b>LINK SHORTENER</b>\n\nDisabled.", reply_markup=action_back(bid))
        if "|" not in text:
            return await query.message.edit_text("❌ Format: <code>API_KEY | vplink.in</code>", reply_markup=action_back(bid))
        api, site = [x.strip() for x in text.split("|", 1)]
        site = site.replace("https://", "").replace("http://", "").rstrip("/")
        update_bot(bid, shortener_api=api, base_site=site)
        return await query.message.edit_text("🔗 <b>LINK SHORTENER</b>\n\nAPI and base site saved for this clone.", reply_markup=action_back(bid))

    if action == "startpic":
        await query.answer()
        ans = await client.ask(query.from_user.id, "🖼️ Send image URL for the clone start photo. Send <code>off</code> to reset to default.", timeout=120)
        text = (ans.text or "").strip()
        if text.lower() == "off":
            update_bot(bid, start_pic=None)
            return await query.message.edit_text("🖼️ <b>START PHOTO</b>\n\nReset to default photo.", reply_markup=action_back(bid))
        if not text.startswith(("http://", "https://")):
            return await query.message.edit_text("❌ URL must start with http:// or https://", reply_markup=action_back(bid))
        update_bot(bid, start_pic=text)
        return await query.message.edit_text("🖼️ <b>START PHOTO</b>\n\nCustom start photo updated successfully.", reply_markup=action_back(bid))

    if action == "transfer":
        return await edit_setting(query, bid, "🔄 <b>TRANSFER DB</b>", "Ownership transfer requires an explicit target user ID. Use the master command workflow when this is needed.")


@Client.on_callback_query(filters.regex(r"^cad:\d+:(minus|plus|noop)$"))
async def auto_delete_time(client, query):
    _, raw, op = query.data.split(":")
    bid = int(raw)
    if not owns(query.from_user.id, bid): return await query.answer("❌ Access denied.", show_alert=True)
    d = get_bot(bid) or {}
    minutes = max(1, min(1440, int(d.get("auto_delete_minutes", 15) or 15)))
    if op == "minus": minutes = max(1, minutes - 1)
    if op == "plus": minutes = min(1440, minutes + 1)
    update_bot(bid, auto_delete_minutes=minutes)
    state = bool(d.get("auto_delete_enabled", False))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➖ 1 MIN", callback_data=f"cad:{bid}:minus"), InlineKeyboardButton(f"⏱ {minutes} MIN", callback_data=f"cad:{bid}:noop"), InlineKeyboardButton("➕ 1 MIN", callback_data=f"cad:{bid}:plus")], [InlineKeyboardButton("‹ BACK", callback_data=f"manage_clone:{bid}")]])
    await query.message.edit_text(f"🗑️ <b>AUTO DELETE</b>\n\nStatus: <b>{'ON' if state else 'OFF'}</b>\nTime: <code>{minutes}</code> minutes", reply_markup=kb)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^cmdelete:\d+$"))
async def clone_delete(client, query):
    bid = int(query.data.split(":")[1])
    if not owns(query.from_user.id, bid): return await query.answer("❌ Access denied.", show_alert=True)
    m = db()
    if m: m.bots.delete_one({"bot_id": bid, "user_id": int(query.from_user.id)} if not is_admin(query.from_user.id) else {"bot_id": bid})
    await query.message.edit_text("🗑️ <b>Clone removed from the manager database.</b>")
    await query.answer("Deleted")
