# ASH FILE STORE & CLONE MANAGER - MASTER BOT ADMIN PANEL & SUSPENSION SYSTEM
import time
import datetime
import math
import re
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from clone_plugins.sessions import (
    start_user_session, is_user_session_active, clear_user_session, cancel_all_listeners
)
from config import ADMINS, BOT_USERNAME

PAGE_SIZE = 6

def db():
    from plugins.clone import mongo_db
    return mongo_db

def is_master_admin(uid) -> bool:
    """Return True if user is a Master Bot Owner or Master Bot Admin."""
    try:
        uid_int = int(uid)
        # Check config ADMINS
        for a in ADMINS:
            if str(a).strip().lstrip("-").isdigit() and int(a) == uid_int:
                return True
        # Check DB master admins
        m = db()
        if m is not None:
            if m.master_admins.find_one({"user_id": uid_int}):
                return True
    except Exception:
        pass
    return False

def is_master_owner(uid) -> bool:
    """Return True if user is primary owner from config ADMINS."""
    try:
        uid_int = int(uid)
        for a in ADMINS:
            if str(a).strip().lstrip("-").isdigit() and int(a) == uid_int:
                return True
    except Exception:
        pass
    return False

def get_all_admins():
    """Returns list of all admin dicts including primary owners and DB added admins."""
    admins = []
    seen = set()
    for a in ADMINS:
        if str(a).strip().lstrip("-").isdigit():
            uid = int(a)
            if uid not in seen:
                seen.add(uid)
                admins.append({
                    "user_id": uid,
                    "name": "Master Owner",
                    "username": "",
                    "is_primary": True,
                    "added_at": None
                })
    m = db()
    if m is not None:
        for doc in m.master_admins.find():
            uid = int(doc["user_id"])
            if uid not in seen:
                seen.add(uid)
                admins.append({
                    "user_id": uid,
                    "name": doc.get("name", "Admin"),
                    "username": doc.get("username", ""),
                    "is_primary": False,
                    "added_at": doc.get("added_at")
                })
    return admins

def add_master_admin(user_id: int, name: str, username: str, added_by: str):
    m = db()
    if m is not None:
        m.master_admins.update_one(
            {"user_id": int(user_id)},
            {"$set": {
                "user_id": int(user_id),
                "name": name,
                "username": username or "",
                "added_by": added_by,
                "added_at": time.time()
            }},
            upsert=True
        )

def remove_master_admin(user_id: int):
    m = db()
    if m is not None:
        m.master_admins.delete_one({"user_id": int(user_id)})

# ----------------- DURATION PARSER ----------------- #

def parse_suspend_duration(text: str):
    """
    Parses duration string like:
    10s, 30s
    1m, 5m
    1h, 12h
    1d, 7d
    1w, 2w
    1mo, 2month, 1month
    1y, 1year
    permanent, forever
    Returns (seconds_int, duration_str) or (None, None) if invalid.
    """
    text = text.strip().lower()
    if text in ("permanent", "forever", "perm", "inf", "infinity", "hamesha"):
        return None, "Permanent"

    # Match number + unit
    match = re.match(r"^(\d+)\s*([a-zA-Z]+)$", text)
    if not match:
        return None, None

    val = int(match.group(1))
    unit = match.group(2)

    if unit in ("s", "sec", "secs", "second", "seconds"):
        return val, f"{val} Second(s)"
    elif unit in ("m", "min", "mins", "minute", "minutes"):
        return val * 60, f"{val} Minute(s)"
    elif unit in ("h", "hr", "hrs", "hour", "hours"):
        return val * 3600, f"{val} Hour(s)"
    elif unit in ("d", "day", "days"):
        return val * 86400, f"{val} Day(s)"
    elif unit in ("w", "wk", "wks", "week", "weeks"):
        return val * 7 * 86400, f"{val} Week(s)"
    elif unit in ("mo", "mon", "month", "months"):
        return val * 30 * 86400, f"{val} Month(s)"
    elif unit in ("y", "yr", "yrs", "year", "years"):
        return val * 365 * 86400, f"{val} Year(s)"

    return None, None

# ----------------- SUSPENSION HELPERS ----------------- #

def is_clone_bot_suspended(bot_id: int):
    """Checks if a clone bot is currently suspended. Handles automatic expiry."""
    m = db()
    if m is None:
        return False, {}
    try:
        doc = m.bots.find_one({"bot_id": int(bot_id)})
        if not doc:
            return False, {}
        if doc.get("suspended"):
            until = doc.get("suspended_until")
            if until and isinstance(until, (int, float)):
                if time.time() >= float(until):
                    # Auto-unsuspend after expiry
                    m.bots.update_one({"_id": doc["_id"]}, {"$set": {"suspended": False, "suspended_until": None}})
                    return False, {}
            return True, doc
    except Exception:
        pass
    return False, {}

def suspend_clone_bot(bot_id: int, duration_secs, duration_str: str, admin_user, admin_username: str):
    m = db()
    if m is not None:
        until_ts = (time.time() + duration_secs) if duration_secs is not None and duration_secs > 0 else None
        m.bots.update_one(
            {"bot_id": int(bot_id)},
            {"$set": {
                "suspended": True,
                "suspended_until": until_ts,
                "suspend_duration_str": duration_str,
                "suspended_by": admin_username or str(getattr(admin_user, "id", "Admin")),
                "suspended_at": time.time()
            }}
        )

def unsuspend_clone_bot(bot_id: int):
    m = db()
    if m is not None:
        m.bots.update_one(
            {"bot_id": int(bot_id)},
            {"$set": {
                "suspended": False,
                "suspended_until": None,
                "unsuspended_at": time.time()
            }}
        )

# Helper to resolve user name/username from Telegram and DB
async def resolve_user_display(client, uid: int, m_db):
    name = None
    username = None
    try:
        # Check DB first
        if m_db is not None and hasattr(m_db, "users"):
            u_doc = m_db.users.find_one({"id": int(uid)}) or m_db.users.find_one({"_id": int(uid)})
            if u_doc:
                name = u_doc.get("name")
                username = u_doc.get("username")
    except Exception:
        pass

    # If name is missing or generic, fetch from telegram
    if not name or name.lower().startswith("user "):
        try:
            u_obj = await client.get_users(int(uid))
            if u_obj:
                name = (f"{u_obj.first_name or ''} {u_obj.last_name or ''}").strip() or u_obj.first_name or f"User {uid}"
                username = u_obj.username or ""
                # Cache in DB
                if m_db is not None and hasattr(m_db, "users"):
                    m_db.users.update_one(
                        {"id": int(uid)},
                        {"$set": {"name": name, "username": username}},
                        upsert=True
                    )
        except Exception:
            if not name:
                name = f"User {uid}"

    return name or f"User {uid}", username or ""

# ----------------- MARKUPS ----------------- #

def admin_panel_main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 SEE ALL CLONE OWNERS", callback_data="admin_all_owners:0")],
        [InlineKeyboardButton("🔍 SEARCH CLONE OWNER", callback_data="admin_search_owner")],
        [InlineKeyboardButton("➕ ADD / MANAGE ADMINS", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("‹ BACK TO HOME", callback_data="start")]
    ])

def admin_manage_admins_markup(admins):
    rows = []
    rows.append([InlineKeyboardButton("➕ ADD NEW MASTER ADMIN", callback_data="admin_add_admin_prompt")])
    for a in admins:
        uid = a["user_id"]
        name = a["name"]
        uname = f"@{a['username']}" if a.get("username") else str(uid)
        if a.get("is_primary"):
            rows.append([InlineKeyboardButton(f"👑 {name} ({uname}) [OWNER]", callback_data="admin_noop")])
        else:
            rows.append([
                InlineKeyboardButton(f"👮 {name} ({uname})", callback_data="admin_noop"),
                InlineKeyboardButton("❌ REMOVE", callback_data=f"admin_rem_admin:{uid}")
            ])
    rows.append([InlineKeyboardButton("‹ BACK TO ADMIN PANEL", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(rows)

def admin_owners_list_markup(owners, page: int, total_pages: int):
    rows = []
    for o in owners:
        uid = o["user_id"]
        name = o.get("name") or "User"
        uname = f"@{o['username']}" if o.get("username") else f"ID: {uid}"
        count = o.get("bot_count", 1)
        rows.append([
            InlineKeyboardButton(f"👤 {name} ({uname}) — {count} Bot(s)", callback_data=f"admin_view_owner:{uid}")
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ PREV", callback_data=f"admin_all_owners:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{max(1, total_pages)}", callback_data="admin_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("NEXT ▶", callback_data=f"admin_all_owners:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton("🔍 SEARCH OWNER", callback_data="admin_search_owner"),
        InlineKeyboardButton("‹ ADMIN PANEL", callback_data="admin_panel_main")
    ])
    return InlineKeyboardMarkup(rows)

def admin_owner_clones_markup(owner_id: int, bots: list):
    rows = []
    for b in bots:
        bid = b["bot_id"]
        bname = b.get("name") or b.get("username") or str(bid)
        status_tag = "⛔ SUSPENDED" if b.get("suspended") else ("⏸ DEACTIVATED" if b.get("deactivated") else "✅ ACTIVE")
        rows.append([
            InlineKeyboardButton(f"🤖 @{bname} [{status_tag}] ↗", callback_data=f"admin_manage_clone:{bid}")
        ])
    rows.append([InlineKeyboardButton("‹ BACK TO ALL OWNERS", callback_data="admin_all_owners:0")])
    return InlineKeyboardMarkup(rows)

def admin_manage_single_clone_markup(bot_doc: dict):
    bid = bot_doc["bot_id"]
    owner_id = bot_doc.get("user_id")
    is_susp = bool(bot_doc.get("suspended"))
    is_deact = bool(bot_doc.get("deactivated"))

    rows = []
    if is_susp:
        rows.append([InlineKeyboardButton("✅ UN-SUSPEND CLONE BOT", callback_data=f"admin_unsuspend_act:{bid}")])
    else:
        rows.append([InlineKeyboardButton("⛔ SUSPEND CLONE BOT (TEMPORARY/PERMANENT)", callback_data=f"admin_suspend_menu:{bid}")])

    rows.append([
        InlineKeyboardButton("⚡ BOT STATUS (ACTIVE / DEACTIVATE)", callback_data=f"cset_active_deactive:{bid}")
    ])
    rows.append([
        InlineKeyboardButton("⚙️ CONFIGURE ALL BOT SETTINGS", callback_data=f"manage_clone:{bid}")
    ])
    rows.append([
        InlineKeyboardButton("🗑️ FORCE DELETE CLONE BOT", callback_data=f"admin_force_del:{bid}")
    ])
    rows.append([
        InlineKeyboardButton("‹ BACK TO USER'S CLONES", callback_data=f"admin_view_owner:{owner_id}")
    ])
    return InlineKeyboardMarkup(rows)

def admin_suspend_menu_markup(bid: int):
    """Clean in-place suspension menu with 1-click preset durations and custom time option."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ 10s", callback_data=f"admin_susp_dur:{bid}:10:10 Seconds"),
            InlineKeyboardButton("⏱ 1m", callback_data=f"admin_susp_dur:{bid}:60:1 Minute"),
            InlineKeyboardButton("⏱ 5m", callback_data=f"admin_susp_dur:{bid}:300:5 Minutes"),
        ],
        [
            InlineKeyboardButton("⏱ 1h", callback_data=f"admin_susp_dur:{bid}:3600:1 Hour"),
            InlineKeyboardButton("⏱ 12h", callback_data=f"admin_susp_dur:{bid}:43200:12 Hours"),
            InlineKeyboardButton("⏱ 1d", callback_data=f"admin_susp_dur:{bid}:86400:1 Day"),
        ],
        [
            InlineKeyboardButton("⏱ 7d", callback_data=f"admin_susp_dur:{bid}:604800:7 Days"),
            InlineKeyboardButton("⏱ 1mo", callback_data=f"admin_susp_dur:{bid}:2592000:1 Month"),
            InlineKeyboardButton("⏱ 1y", callback_data=f"admin_susp_dur:{bid}:31536000:1 Year"),
        ],
        [
            InlineKeyboardButton("⛔ PERMANENT", callback_data=f"admin_susp_dur:{bid}:0:Permanent"),
            InlineKeyboardButton("✍️ CUSTOM TIME", callback_data=f"admin_susp_custom:{bid}"),
        ],
        [
            InlineKeyboardButton("‹ BACK TO BOT", callback_data=f"admin_manage_clone:{bid}")
        ]
    ])

# ----------------- CALLBACK HANDLER ----------------- #

async def handle_admin_panel_callbacks(client, query):
    user_id = query.from_user.id
    if not is_master_admin(user_id):
        return await query.answer("❌ Access denied. Master Bot Admins only.", show_alert=True)

    data = query.data
    m = db()

    # 1. Main Admin Panel
    if data == "admin_panel_main":
        cancel_all_listeners(client, query.message.chat.id, user_id)
        total_owners = 0
        total_bots = 0
        if m is not None:
            total_bots = m.bots.count_documents({})
            pipeline = [{"$group": {"_id": "$user_id"}}, {"$count": "total"}]
            agg = list(m.bots.aggregate(pipeline))
            total_owners = agg[0]["total"] if agg else 0

        admin_count = len(get_all_admins())
        text = (
            "👑 <b>MASTER BOT ADMIN CONTROL PANEL</b>\n\n"
            "<blockquote>Welcome Administrator! Control and supervise all cloned bots, search clone owners, manage suspension, and configure bot settings.</blockquote>\n\n"
            f"📊 <b>TOTAL CLONE OWNERS:</b> <code>{total_owners} Users</code>\n"
            f"🤖 <b>TOTAL CLONE BOTS:</b> <code>{total_bots} Bots</code>\n"
            f"👮 <b>MASTER BOT ADMINS:</b> <code>{admin_count} Admins</code>\n\n"
            "<i>Select an option from the menu below:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_panel_main_markup())

    # 2. All Clone Owners List
    if data.startswith("admin_all_owners"):
        cancel_all_listeners(client, query.message.chat.id, user_id)
        page = 0
        if ":" in data:
            try:
                page = int(data.split(":")[1])
            except Exception:
                page = 0

        owners = []
        total_owners = 0
        if m is not None:
            pipeline = [
                {"$group": {"_id": "$user_id", "bot_count": {"$sum": 1}, "latest_doc": {"$last": "$$ROOT"}}},
                {"$sort": {"bot_count": -1}}
            ]
            agg = list(m.bots.aggregate(pipeline))
            total_owners = len(agg)
            total_pages = max(1, math.ceil(total_owners / PAGE_SIZE))
            page = max(0, min(page, total_pages - 1))
            page_items = agg[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

            for item in page_items:
                uid = item["_id"]
                count = item["bot_count"]
                name, uname = await resolve_user_display(client, uid, m)
                owners.append({
                    "user_id": uid,
                    "name": name,
                    "username": uname,
                    "bot_count": count
                })
        else:
            total_pages = 1

        text = (
            "👥 <b>ALL CLONE OWNERS DIRECTORY</b>\n\n"
            f"<b>📊 Total Registered Owners:</b> <code>{total_owners}</code>\n"
            f"<b>📄 Page:</b> <code>{page+1}/{total_pages}</code>\n\n"
            "<i>Click on any user below to view and manage all their cloned bots:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_owners_list_markup(owners, page, total_pages))

    # 3. View specific Owner's Clones
    if data.startswith("admin_view_owner:"):
        cancel_all_listeners(client, query.message.chat.id, user_id)
        owner_id = int(data.split(":")[1])
        bots = list(m.bots.find({"user_id": owner_id})) if m is not None else []
        name, uname = await resolve_user_display(client, owner_id, m)
        owner_uname = f"@{uname}" if uname else f"ID: {owner_id}"

        text = (
            f"👤 <b>CLONE OWNER DETAILS:</b>\n\n"
            f"<b>• Name:</b> {name}\n"
            f"<b>• Username/ID:</b> <code>{owner_uname}</code>\n"
            f"<b>• Total Clones:</b> <code>{len(bots)} Bot(s)</code>\n\n"
            "<i>Select any clone bot below to inspect details, configure its settings, or apply suspension:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_owner_clones_markup(owner_id, bots))

    # 4. Manage Specific Clone Bot
    if data.startswith("admin_manage_clone:"):
        cancel_all_listeners(client, query.message.chat.id, user_id)
        bid = int(data.split(":")[1])
        bot_doc = m.bots.find_one({"bot_id": bid}) if m is not None else None
        if not bot_doc:
            return await query.answer("❌ Clone bot not found in database.", show_alert=True)

        bot_name = bot_doc.get("name") or bot_doc.get("username") or str(bid)
        bot_username = bot_doc.get("username") or "None"
        owner_id = bot_doc.get("user_id", 0)
        owner_name, owner_uname = await resolve_user_display(client, owner_id, m)
        owner_str = f"{owner_name} (@{owner_uname})" if owner_uname else f"{owner_name} ({owner_id})"

        is_susp = bool(bot_doc.get("suspended"))
        is_deact = bool(bot_doc.get("deactivated"))

        if is_susp:
            status_text = "⛔ <b>SUSPENDED</b>"
            until = bot_doc.get("suspended_until")
            if until:
                exp_dt = datetime.datetime.fromtimestamp(until).strftime("%Y-%m-%d %H:%M:%S UTC")
                dur_str = bot_doc.get("suspend_duration_str", "Temporary")
                status_text += f" (Until <code>{exp_dt}</code> - {dur_str})"
            else:
                status_text += " (Permanent)"
            status_text += f"\n<b>Suspended By:</b> @{bot_doc.get('suspended_by', 'Admin')}"
        elif is_deact:
            status_text = "⏸ <b>DEACTIVATED</b>"
        else:
            status_text = "✅ <b>ACTIVE & RUNNING</b>"

        last_act = bot_doc.get("last_active_time")
        last_act_str = datetime.datetime.fromtimestamp(last_act).strftime("%Y-%m-%d %H:%M:%S UTC") if last_act else "Never"

        text = (
            f"🤖 <b>CLONE BOT SUPERVISION: @{bot_username}</b>\n\n"
            f"<b>• Bot Name:</b> {bot_name}\n"
            f"<b>• Bot ID:</b> <code>{bid}</code>\n"
            f"<b>• Owner:</b> {owner_str}\n"
            f"<b>• Current Status:</b> {status_text}\n"
            f"<b>• Last Active:</b> <code>{last_act_str}</code>\n\n"
            "<i>Use the action buttons below to manage this clone bot:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_manage_single_clone_markup(bot_doc))

    # 5. Suspend Clone Menu (In-Place Edit with 1-Click Duration Buttons)
    if data.startswith("admin_suspend_menu:"):
        bid = int(data.split(":")[1])
        bot_doc = m.bots.find_one({"bot_id": bid}) if m is not None else None
        if not bot_doc:
            return await query.answer("❌ Clone bot not found.", show_alert=True)

        cancel_all_listeners(client, query.message.chat.id, user_id)
        bot_username = bot_doc.get("username") or str(bid)

        menu_text = (
            f"⛔ <b>SUSPEND CLONE BOT: @{bot_username}</b>\n\n"
            "<blockquote>Select a suspension duration below for 1-click instant suspension, or click Custom Time to enter any exact duration.</blockquote>\n\n"
            "<b>Choose duration:</b>"
        )
        return await query.message.edit_text(menu_text, reply_markup=admin_suspend_menu_markup(bid))

    # 5.1 One-Click Preset Duration Action
    if data.startswith("admin_susp_dur:"):
        parts = data.split(":")
        bid = int(parts[1])
        secs = int(parts[2])
        dur_str = parts[3]

        bot_doc = m.bots.find_one({"bot_id": bid}) if m is not None else None
        if not bot_doc:
            return await query.answer("❌ Bot not found.", show_alert=True)

        admin_uname = query.from_user.username or query.from_user.first_name or "Administrator"
        suspend_clone_bot(bid, secs if secs > 0 else None, dur_str, query.from_user, admin_uname)

        bot_username = bot_doc.get("username") or str(bid)
        until_str = datetime.datetime.fromtimestamp(time.time() + secs).strftime("%Y-%m-%d %H:%M:%S UTC") if secs > 0 else "Permanent"

        # Notify Clone Owner
        owner_id = bot_doc.get("user_id")
        if owner_id:
            notice_text = (
                f"⛔ <b>YOUR CLONE BOT @{bot_username} HAS BEEN SUSPENDED!</b>\n\n"
                f"<i>Your clone bot has been suspended by Master Bot Administrator (@{admin_uname}).</i>\n\n"
                f"<b>⏱ Duration:</b> <code>{dur_str}</code>\n"
                f"<b>⏳ Expiry Time:</b> <code>{until_str}</code>\n"
                f"<b>👮 Administrator:</b> @{admin_uname}\n\n"
                f"<i>If you have any questions or would like to appeal, please contact @{admin_uname}.</i>"
            )
            try:
                btn_rows = []
                if admin_uname and not admin_uname.startswith("User"):
                    btn_rows.append([InlineKeyboardButton("💬 CONTACT ADMIN", url=f"https://t.me/{admin_uname.lstrip('@')}")])
                await client.send_message(
                    chat_id=int(owner_id),
                    text=notice_text,
                    reply_markup=InlineKeyboardMarkup(btn_rows) if btn_rows else None
                )
            except Exception:
                pass

        # Notify Log channel
        log_ch = bot_doc.get("log_channel")
        if log_ch:
            try:
                await client.send_message(int(log_ch), f"⛔ <b>Bot @{bot_username} suspended for {dur_str} by Admin @{admin_uname}.</b>")
            except Exception:
                pass

        await query.answer(f"✅ Bot @{bot_username} suspended for {dur_str}!", show_alert=True)

        # Refresh single clone view
        fresh_doc = m.bots.find_one({"bot_id": bid})
        owner_name, owner_uname = await resolve_user_display(client, fresh_doc.get("user_id", 0), m)
        owner_str = f"{owner_name} (@{owner_uname})" if owner_uname else f"{owner_name} ({fresh_doc.get('user_id', 0)})"
        last_act = fresh_doc.get("last_active_time")
        last_act_str = datetime.datetime.fromtimestamp(last_act).strftime("%Y-%m-%d %H:%M:%S UTC") if last_act else "Never"

        status_text = "⛔ <b>SUSPENDED</b>"
        if secs > 0:
            status_text += f" (Until <code>{until_str}</code> - {dur_str})"
        else:
            status_text += " (Permanent)"
        status_text += f"\n<b>Suspended By:</b> @{admin_uname}"

        text = (
            f"🤖 <b>CLONE BOT SUPERVISION: @{bot_username}</b>\n\n"
            f"<b>• Bot Name:</b> {fresh_doc.get('name') or bot_username}\n"
            f"<b>• Bot ID:</b> <code>{bid}</code>\n"
            f"<b>• Owner:</b> {owner_str}\n"
            f"<b>• Current Status:</b> {status_text}\n"
            f"<b>• Last Active:</b> <code>{last_act_str}</code>\n\n"
            "<i>Use the action buttons below to manage this clone bot:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_manage_single_clone_markup(fresh_doc))

    # 5.2 Custom Time Input Prompt
    if data.startswith("admin_susp_custom:"):
        bid = int(data.split(":")[1])
        bot_doc = m.bots.find_one({"bot_id": bid}) if m is not None else None
        if not bot_doc:
            return await query.answer("❌ Clone bot not found.", show_alert=True)

        cancel_all_listeners(client, query.message.chat.id, user_id)
        sess_token = start_user_session(user_id, f"admin_suspend_{bid}")
        bot_username = bot_doc.get("username") or str(bid)

        prompt_text = (
            f"⛔ <b>ENTER CUSTOM SUSPENSION TIME: @{bot_username}</b>\n\n"
            "Please send the exact duration you want to suspend this bot:\n\n"
            "<b>Format Examples:</b>\n"
            "• <code>10s</code> = 10 Seconds\n"
            "• <code>1m</code> or <code>5m</code> = 1 or 5 Minutes\n"
            "• <code>1h</code> or <code>12h</code> = 1 or 12 Hours\n"
            "• <code>1d</code> or <code>7d</code> = 1 or 7 Days\n"
            "• <code>1w</code> or <code>2w</code> = 1 or 2 Weeks\n"
            "• <code>1mo</code> or <code>1month</code> = 1 Month\n"
            "• <code>1y</code> or <code>1year</code> = 1 Year\n"
            "• <code>permanent</code> = Permanent Suspension\n\n"
            "<i>Send /cancel or click Cancel below to abort.</i>"
        )
        await query.message.edit_text(
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data=f"admin_manage_clone:{bid}")]])
        )

        async def _listen_custom_suspend():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await query.message.edit_text("❌ <b>Session timed out.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO BOT", callback_data=f"admin_manage_clone:{bid}")]]))
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            try:
                await ans.delete()
            except Exception:
                pass
            if txt == "/cancel":
                clear_user_session(user_id)
                return await query.message.edit_text("❌ <b>Suspension cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO BOT", callback_data=f"admin_manage_clone:{bid}")]]))

            secs, dur_str = parse_suspend_duration(txt)
            if dur_str is None:
                clear_user_session(user_id)
                return await query.message.edit_text(
                    "❌ <b>Invalid duration format!</b> Please use formats like <code>10s</code>, <code>5m</code>, <code>1h</code>, <code>1d</code>, <code>1mo</code>, <code>1y</code>, or <code>permanent</code>.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 TRY AGAIN", callback_data=f"admin_susp_custom:{bid}")], [InlineKeyboardButton("‹ BACK TO BOT", callback_data=f"admin_manage_clone:{bid}")]])
                )

            admin_uname = query.from_user.username or query.from_user.first_name or "Administrator"
            suspend_clone_bot(bid, secs, dur_str, query.from_user, admin_uname)
            clear_user_session(user_id)

            until_str = datetime.datetime.fromtimestamp(time.time() + secs).strftime("%Y-%m-%d %H:%M:%S UTC") if secs else "Permanent"

            # Notify Clone Owner
            owner_id = bot_doc.get("user_id")
            if owner_id:
                notice_text = (
                    f"⛔ <b>YOUR CLONE BOT @{bot_username} HAS BEEN SUSPENDED!</b>\n\n"
                    f"<i>Your clone bot has been suspended by Master Bot Administrator (@{admin_uname}).</i>\n\n"
                    f"<b>⏱ Duration:</b> <code>{dur_str}</code>\n"
                    f"<b>⏳ Expiry Time:</b> <code>{until_str}</code>\n"
                    f"<b>👮 Administrator:</b> @{admin_uname}\n\n"
                    f"<i>If you have any questions or would like to appeal, please contact @{admin_uname}.</i>"
                )
                try:
                    btn_rows = []
                    if admin_uname and not admin_uname.startswith("User"):
                        btn_rows.append([InlineKeyboardButton("💬 CONTACT ADMIN", url=f"https://t.me/{admin_uname.lstrip('@')}")])
                    await client.send_message(
                        chat_id=int(owner_id),
                        text=notice_text,
                        reply_markup=InlineKeyboardMarkup(btn_rows) if btn_rows else None
                    )
                except Exception:
                    pass

            # Notify Clone Bot Log channel if set
            log_ch = bot_doc.get("log_channel")
            if log_ch:
                try:
                    await client.send_message(int(log_ch), f"⛔ <b>Bot @{bot_username} has been suspended by Admin @{admin_uname}.</b>")
                except Exception:
                    pass

            try:
                await query.answer(f"✅ Bot @{bot_username} suspended for {dur_str}!", show_alert=True)
            except Exception:
                pass

            # Refresh single clone view
            fresh_doc = m.bots.find_one({"bot_id": bid})
            owner_name, owner_uname = await resolve_user_display(client, fresh_doc.get("user_id", 0), m)
            owner_str = f"{owner_name} (@{owner_uname})" if owner_uname else f"{owner_name} ({fresh_doc.get('user_id', 0)})"
            last_act = fresh_doc.get("last_active_time")
            last_act_str = datetime.datetime.fromtimestamp(last_act).strftime("%Y-%m-%d %H:%M:%S UTC") if last_act else "Never"

            status_text = "⛔ <b>SUSPENDED</b>"
            if secs and secs > 0:
                status_text += f" (Until <code>{until_str}</code> - {dur_str})"
            else:
                status_text += " (Permanent)"
            status_text += f"\n<b>Suspended By:</b> @{admin_uname}"

            text = (
                f"🤖 <b>CLONE BOT SUPERVISION: @{bot_username}</b>\n\n"
                f"<b>• Bot Name:</b> {fresh_doc.get('name') or bot_username}\n"
                f"<b>• Bot ID:</b> <code>{bid}</code>\n"
                f"<b>• Owner:</b> {owner_str}\n"
                f"<b>• Current Status:</b> {status_text}\n"
                f"<b>• Last Active:</b> <code>{last_act_str}</code>\n\n"
                "<i>Use the action buttons below to manage this clone bot:</i>"
            )
            await query.message.edit_text(text, reply_markup=admin_manage_single_clone_markup(fresh_doc))

        asyncio.create_task(_listen_custom_suspend())
        return

    # 6. Unsuspend Clone Bot
    if data.startswith("admin_unsuspend_act:"):
        bid = int(data.split(":")[1])
        bot_doc = m.bots.find_one({"bot_id": bid}) if m is not None else None
        if not bot_doc:
            return await query.answer("❌ Clone bot not found.", show_alert=True)

        unsuspend_clone_bot(bid)
        bot_username = bot_doc.get("username") or str(bid)
        admin_uname = query.from_user.username or query.from_user.first_name or "Administrator"

        # Notify owner
        owner_id = bot_doc.get("user_id")
        if owner_id:
            try:
                await client.send_message(
                    chat_id=int(owner_id),
                    text=(
                        f"✅ <b>YOUR CLONE BOT @{bot_username} HAS BEEN UN-SUSPENDED!</b>\n\n"
                        f"<i>Master Bot Administrator (@{admin_uname}) has lifted the suspension on your bot.\n\n"
                        f"Your clone bot is now fully functional and active again!</i>"
                    )
                )
            except Exception:
                pass

        await query.answer("✅ Bot unsuspended successfully!", show_alert=True)
        # Refresh UI
        fresh_doc = m.bots.find_one({"bot_id": bid})
        owner_name, owner_uname = await resolve_user_display(client, fresh_doc.get("user_id", 0), m)
        owner_str = f"{owner_name} (@{owner_uname})" if owner_uname else f"{owner_name} ({fresh_doc.get('user_id', 0)})"
        last_act = fresh_doc.get("last_active_time")
        last_act_str = datetime.datetime.fromtimestamp(last_act).strftime("%Y-%m-%d %H:%M:%S UTC") if last_act else "Never"

        is_deact = bool(fresh_doc.get("deactivated"))
        status_text = "⏸ <b>DEACTIVATED</b>" if is_deact else "✅ <b>ACTIVE & RUNNING</b>"

        text = (
            f"🤖 <b>CLONE BOT SUPERVISION: @{bot_username}</b>\n\n"
            f"<b>• Bot Name:</b> {fresh_doc.get('name') or bot_username}\n"
            f"<b>• Bot ID:</b> <code>{bid}</code>\n"
            f"<b>• Owner:</b> {owner_str}\n"
            f"<b>• Current Status:</b> {status_text}\n"
            f"<b>• Last Active:</b> <code>{last_act_str}</code>\n\n"
            "<i>Use the action buttons below to manage this clone bot:</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_manage_single_clone_markup(fresh_doc))

    # 7. Search Clone Owner
    if data == "admin_search_owner":
        cancel_all_listeners(client, query.message.chat.id, user_id)
        sess_token = start_user_session(user_id, "admin_search_owner")

        prompt_text = (
            "🔍 <b>SEARCH CLONE OWNER:</b>\n\n"
            "Please send the <b>Telegram User ID</b> (e.g. <code>5550505</code>) or <b>@Username</b> of the user you want to find:\n\n"
            "<i>Send /cancel to abort search.</i>"
        )
        await query.message.edit_text(
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data="admin_panel_main")]])
        )

        async def _listen_search():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Search timed out.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                clear_user_session(user_id)
                return await client.send_message(user_id, "❌ <b>Search cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ ADMIN PANEL", callback_data="admin_panel_main")]]))

            clear_user_session(user_id)
            target_uid = None
            if txt.lstrip("-").isdigit():
                target_uid = int(txt)
            elif txt.startswith("@"):
                uname = txt.lstrip("@").lower()
                # Search users in DB or pyrogram
                u_doc = m.users.find_one({"username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}}) if m is not None and hasattr(m, "users") else None
                if u_doc:
                    target_uid = int(u_doc["id"])
                else:
                    b_doc = m.bots.find_one({"owner_username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}}) if m is not None else None
                    if b_doc:
                        target_uid = int(b_doc["user_id"])
                    else:
                        try:
                            resolved = await client.get_users(txt)
                            target_uid = resolved.id
                        except Exception:
                            target_uid = None
            else:
                try:
                    resolved = await client.get_users(txt)
                    target_uid = resolved.id
                except Exception:
                    target_uid = None

            if not target_uid:
                return await client.send_message(
                    user_id,
                    f"❌ <b>User '{txt}' not found!</b> Please verify the User ID or username.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 SEARCH AGAIN", callback_data="admin_search_owner")]])
                )

            # Find clones of target_uid
            bots = list(m.bots.find({"user_id": target_uid})) if m is not None else []
            count = len(bots)

            name_str, uname_str = await resolve_user_display(client, target_uid, m)
            uname_display = f"@{uname_str}" if uname_str else f"ID: {target_uid}"

            if count == 0:
                text = (
                    f"👤 <b>USER SEARCH RESULT:</b>\n\n"
                    f"<b>• User:</b> {name_str}\n"
                    f"<b>• Username:</b> <code>{uname_display}</code>\n"
                    f"<b>• User ID:</b> <code>{target_uid}</code>\n\n"
                    f"⚠️ <b>This user has not cloned any bots yet.</b>"
                )
                buttons = [
                    [InlineKeyboardButton("🔍 SEARCH ANOTHER", callback_data="admin_search_owner")],
                    [InlineKeyboardButton("‹ ADMIN PANEL", callback_data="admin_panel_main")]
                ]
            else:
                text = (
                    f"👤 <b>CLONE OWNER FOUND:</b>\n\n"
                    f"<b>• Name:</b> {name_str}\n"
                    f"<b>• Username:</b> <code>{uname_display}</code>\n"
                    f"<b>• User ID:</b> <code>{target_uid}</code>\n"
                    f"<b>• Total Clones Created:</b> <code>{count} Bot(s)</code>\n\n"
                    f"<i>Click the button below to view and manage all {count} clone bots:</i>"
                )
                buttons = [
                    [InlineKeyboardButton(f"🤖 SEE ALL CLONES ({count}) ↗", callback_data=f"admin_view_owner:{target_uid}")],
                    [InlineKeyboardButton("🔍 SEARCH ANOTHER", callback_data="admin_search_owner")],
                    [InlineKeyboardButton("‹ ADMIN PANEL", callback_data="admin_panel_main")]
                ]
            await client.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(buttons))

        asyncio.create_task(_listen_search())
        return

    # 8. Manage Master Admins
    if data == "admin_manage_admins":
        cancel_all_listeners(client, query.message.chat.id, user_id)
        if not is_master_owner(user_id):
            return await query.answer("❌ Only Master Bot Owner can manage Admins.", show_alert=True)

        admins = get_all_admins()
        text = (
            "👮 <b>MASTER BOT ADMINS MANAGEMENT</b>\n\n"
            f"<b>Total Admins:</b> <code>{len(admins)}</code>\n\n"
            "<i>Admins have full access to the Admin Panel, clone owner directory, and suspension controls.</i>"
        )
        return await query.message.edit_text(text, reply_markup=admin_manage_admins_markup(admins))

    # 9. Add Master Admin Prompt
    if data == "admin_add_admin_prompt":
        if not is_master_owner(user_id):
            return await query.answer("❌ Only Master Bot Owner can add Admins.", show_alert=True)

        cancel_all_listeners(client, query.message.chat.id, user_id)
        sess_token = start_user_session(user_id, "admin_add_admin")

        prompt_text = (
            "➕ <b>ADD MASTER BOT ADMIN:</b>\n\n"
            "Please send the <b>Telegram User ID</b> or <b>@Username</b> of the person you want to promote as Master Bot Admin:\n\n"
            "<i>Send /cancel to abort.</i>"
        )
        await query.message.edit_text(
            prompt_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ CANCEL", callback_data="admin_manage_admins")]])
        )

        async def _listen_add_admin():
            try:
                ans = await client.listen(chat_id=user_id, timeout=120)
            except Exception:
                await client.send_message(user_id, "❌ <b>Session timed out.</b>")
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return
            txt = (ans.text or "").strip()
            if txt == "/cancel":
                clear_user_session(user_id)
                return await client.send_message(user_id, "❌ <b>Cancelled.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ ADMINS", callback_data="admin_manage_admins")]]))

            clear_user_session(user_id)
            try:
                target_user = await client.get_users(int(txt) if txt.lstrip("-").isdigit() else txt)
            except Exception as e:
                return await client.send_message(
                    user_id,
                    f"❌ <b>Unable to find user '{txt}':</b> {e}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ ADMINS", callback_data="admin_manage_admins")]])
                )

            add_master_admin(
                target_user.id,
                target_user.first_name or "Admin",
                target_user.username or "",
                query.from_user.username or str(user_id)
            )

            # Notify new admin
            try:
                await client.send_message(
                    target_user.id,
                    f"🎉 <b>CONGRATULATIONS!</b>\n\n"
                    f"You have been appointed as a <b>Master Bot Administrator</b> by {query.from_user.mention}!\n\n"
                    f"You now have access to the Admin Panel in @{BOT_USERNAME}."
                )
            except Exception:
                pass

            await client.send_message(
                user_id,
                f"✅ <b>Successfully added {target_user.mention} (<code>{target_user.id}</code>) as Master Bot Admin!</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👮 VIEW ALL ADMINS", callback_data="admin_manage_admins")]])
            )

        asyncio.create_task(_listen_add_admin())
        return

    # 10. Remove Master Admin
    if data.startswith("admin_rem_admin:"):
        if not is_master_owner(user_id):
            return await query.answer("❌ Only Master Bot Owner can remove Admins.", show_alert=True)
        rem_uid = int(data.split(":")[1])
        remove_master_admin(rem_uid)
        await query.answer("✅ Admin removed successfully.", show_alert=True)
        admins = get_all_admins()
        return await query.message.edit_text(
            f"👮 <b>MASTER BOT ADMINS MANAGEMENT</b>\n\n<b>Total Admins:</b> <code>{len(admins)}</code>",
            reply_markup=admin_manage_admins_markup(admins)
        )

    # 11. Force Delete Clone
    if data.startswith("admin_force_del:"):
        bid = int(data.split(":")[1])
        if m is not None:
            m.bots.delete_one({"bot_id": bid})
        await query.answer("🗑️ Clone bot record deleted from database.", show_alert=True)
        return await query.message.edit_text(
            f"🗑️ <b>Clone bot {bid} deleted successfully.</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK TO ALL OWNERS", callback_data="admin_all_owners:0")]])
        )

    await query.answer()
