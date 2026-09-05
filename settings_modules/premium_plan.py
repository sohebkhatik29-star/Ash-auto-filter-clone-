# 💸 PREMIUM PLAN SETTINGS MODULE
import os
import re
import time
import asyncio
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.sessions import start_user_session, is_user_session_active, clear_user_session

def get_contact_info(rec: dict):
    """Return (clean_username, full_url, display_str)."""
    contact = rec.get("premium_screenshot_contact") or rec.get("owner_username") or "movies_1780"
    contact = str(contact).strip()
    if contact.startswith("http://") or contact.startswith("https://"):
        url = contact
        display = contact
        username = contact.rstrip("/").split("/")[-1].lstrip("@")
    else:
        username = contact.lstrip("@")
        url = f"https://t.me/{username}"
        display = f"@{username}"
    return username, url, display

def render_premium_plan_payload(rec: dict, user_mention: str = "User", show_upi: bool = False, payload: str = ""):
    """
    Generate (text, photo_id, reply_markup, has_spoiler, invert_caption)
    matching the exact VJ File Store style shown in user's video.
    """
    _, contact_url, display_contact = get_contact_info(rec)
    has_spoiler = bool(rec.get("premium_spoiler", False))
    invert_caption = bool(rec.get("premium_invert_cap", False))

    back_to_prem_cb = f"c_buy_prem:{payload}" if payload else "c_buy_prem"
    back_to_verify_cb = f"c_prem_user_back:{payload}" if payload else "c_prem_user_back"
    upi_cb = f"c_prem_upi_view:{payload}" if payload else "c_prem_upi_view"

    if show_upi:
        photo_id = rec.get("premium_qr_pic") or rec.get("premium_plan_photo")
        upi_id = rec.get("premium_upi_id") or "sonukhatik7193@oksbi"
        text = (
            "<b>PAYMENT METHOD: UPI ⚡</b>\n\n"
            "<b>YOU CAN PURCHASE PREMIUM THROUGH UPI, NET BANKING.</b>\n\n"
            f"💳 <b>UPI ID -</b> <code>{upi_id}</code>\n\n"
            "❗ <b>MUST SEND SCREENSHOT AFTER PAYMENT.</b>\n\n"
            "‼️ <b>AFTER SENDING SCREENSHOT PLEASE GIVE US SOMETIME TO ADD YOU IN PREMIUM LIST.</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("• SEND PAYMENT SCREENSHOT •", url=contact_url)],
            [InlineKeyboardButton("‹ BACK", callback_data=back_to_prem_cb)]
        ])
    else:
        # Standard plan list: Only use photo if explicitly set for plan list (not UPI QR)
        photo_id = rec.get("premium_plan_photo")
        custom_txt = rec.get("premium_plan_text")
        if custom_txt:
            text = custom_txt.replace("{user_mention}", user_mention).replace("{user}", user_mention)
        else:
            text = (
                "⚡ <b>Buy Movies and Series Premium Now ⚡</b>\n\n"
                "<b>More Premium Plans</b>\n"
                "• 60 Rs - 1 month\n"
                "• 120 Rs - 3 Month\n"
                "• 240 Rs - 6 Months + 15 Days Free\n"
                "• 480 Rs - 1 Year + 1 Month\n"
                "• 1500 Rs - Lifetime\n\n"
                "⚠️ <b>Send Ss After Payment</b> ⚠️\n"
                f"<b>Contact :-</b> {display_contact}"
            )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 UPI", callback_data=upi_cb)],
            [InlineKeyboardButton("• SEND PAYMENT SCREENSHOT •", url=contact_url)],
            [InlineKeyboardButton("‹ BACK", callback_data=back_to_verify_cb)]
        ])

    return text, photo_id, markup, has_spoiler, invert_caption

_UI_BUSY_TRACKER = {}

def _check_and_lock_ui(chat_id, msg_id, action_tag=""):
    """Prevent race conditions / multiple panels when user clicks button multiple times rapidly."""
    if not chat_id or not msg_id:
        return True
    now = time.time()
    # Cleanup old entries (> 5 seconds)
    stale_keys = [k for k, ts in _UI_BUSY_TRACKER.items() if now - ts > 5.0]
    for k in stale_keys:
        _UI_BUSY_TRACKER.pop(k, None)

    key = (chat_id, msg_id, action_tag)
    last_time = _UI_BUSY_TRACKER.get(key, 0)
    if now - last_time < 1.2:
        return False
    _UI_BUSY_TRACKER[key] = now
    return True

async def handle_user_buy_premium_view(client, query_or_msg, rec: dict = None, show_upi: bool = False, payload: str = ""):
    """Display user-facing Premium Plan or UPI details with QR photo and one-tap copy UPI ID."""
    is_query = hasattr(query_or_msg, "message") and hasattr(query_or_msg, "answer")
    user = query_or_msg.from_user if is_query else getattr(query_or_msg, "from_user", None)
    user_mention = getattr(user, "mention", "User") if user else "User"
    user_id = user.id if user else 0
    msg = query_or_msg.message if is_query else query_or_msg
    chat_id = (msg.chat.id if hasattr(msg, "chat") and msg.chat else user_id) if msg else user_id
    msg_id = getattr(msg, "id", 0)

    if is_query:
        try:
            await query_or_msg.answer()
        except Exception:
            pass
        if not _check_and_lock_ui(chat_id, msg_id, f"buy_prem_{show_upi}"):
            return

        if not payload and ":" in str(getattr(query_or_msg, "data", "")):
            try:
                payload = str(query_or_msg.data).split(":", 1)[1]
            except Exception:
                pass

    if not rec:
        try:
            from clone_plugins.commands import bot_record
            rec = bot_record(client)
        except Exception:
            rec = {}

    # Merge with master_settings if any key is missing in clone doc
    try:
        from plugins.clone import mongo_db
        if mongo_db is not None:
            m_rec = mongo_db.master_settings.find_one({"type": "master_config"}) or mongo_db.master_settings.find_one({}) or {}
            if m_rec:
                merged = dict(m_rec)
                if rec:
                    for k, v in rec.items():
                        if v is not None and v != "":
                            merged[k] = v
                rec = merged
    except Exception:
        pass

    text, photo_id, markup, has_spoiler, invert_caption = render_premium_plan_payload(
        rec, user_mention=user_mention, show_upi=show_upi, payload=payload
    )

    # Resolve photo object (local file path or file_id)
    photo_target = None
    if show_upi:
        photo_target = rec.get("premium_qr_path") or rec.get("premium_qr_pic") or rec.get("premium_plan_photo_path") or photo_id
    else:
        photo_target = rec.get("premium_plan_photo_path") or rec.get("premium_plan_photo")

    if photo_target:
        try:
            from settings_modules.thumbnail import get_cached_thumb_path
            cached = await get_cached_thumb_path(client, photo_target)
            if cached and os.path.exists(cached):
                photo_target = cached
        except Exception:
            pass

    if not msg:
        return

    # Scenario A: Target has a PHOTO (e.g. UPI view with QR code)
    if photo_target:
        if is_query and msg and getattr(msg, "photo", None):
            # Already a photo message: edit caption in place!
            try:
                return await msg.edit_caption(
                    caption=text,
                    reply_markup=markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass
        else:
            # Previous message was text: delete old text message and send photo
            if is_query and msg:
                try:
                    await msg.delete()
                except Exception:
                    pass
            try:
                return await client.send_photo(
                    chat_id=chat_id,
                    photo=photo_target,
                    caption=text,
                    reply_markup=markup,
                    parse_mode=enums.ParseMode.HTML,
                    has_spoiler=has_spoiler
                )
            except Exception:
                try:
                    return await client.send_photo(
                        chat_id=chat_id,
                        photo=photo_target,
                        caption=text,
                        reply_markup=markup,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass

    # Scenario B: Target is TEXT only (e.g. Plan list or UPI without QR code)
    if is_query and msg:
        if getattr(msg, "photo", None):
            # Previous message was a photo: delete old photo and send text message
            try:
                await msg.delete()
            except Exception:
                pass
            return await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            # Previous message is text: edit in-place without creating a new message!
            try:
                return await msg.edit_text(
                    text=text,
                    reply_markup=markup,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception:
                pass

    return await client.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )


async def handle_user_back_from_premium(client, query, payload: str = ""):
    """Handle user clicking BACK from Premium/UPI view, reliably restoring verification panel or start menu."""
    user = getattr(query, "from_user", None)
    user_id = user.id if user else 0
    msg = getattr(query, "message", None)
    chat_id = msg.chat.id if (msg and getattr(msg, "chat", None)) else user_id
    msg_id = getattr(msg, "id", 0)

    try:
        await query.answer()
    except Exception:
        pass

    if not _check_and_lock_ui(chat_id, msg_id, "user_back"):
        return

    if not payload and ":" in str(getattr(query, "data", "")):
        try:
            payload = str(query.data).split(":", 1)[1]
        except Exception:
            payload = ""

    # 1. Try to get verification panel (clone first, then master)
    v_text, v_markup = None, None
    try:
        from clone_plugins.commands import access_verification
        v_res = await access_verification(client, user_id, payload)
        if isinstance(v_res, (tuple, list)):
            v_text = v_res[0]
            v_markup = v_res[1] if len(v_res) > 1 else None
        elif v_res:
            v_text, v_markup = "<b>🔐 Please verify first to access this file.</b>", v_res
    except Exception:
        pass

    if not v_markup:
        try:
            from plugins.commands import check_master_verification
            v_text, v_markup = await check_master_verification(client, user_id, payload)
        except Exception:
            pass

    if v_text and v_markup:
        # If current message is text, EDIT IN-PLACE! Never create a new message.
        if msg and not getattr(msg, "photo", None):
            try:
                return await msg.edit_text(
                    text=v_text,
                    reply_markup=v_markup,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception:
                try:
                    return await msg.edit_text(
                        text=v_text,
                        reply_markup=v_markup,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

        # If current message is a photo (e.g. from UPI view), delete old photo & send text message
        if msg:
            try:
                await msg.delete()
            except Exception:
                pass
        try:
            return await client.send_message(
                chat_id=chat_id,
                text=v_text,
                reply_markup=v_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            try:
                return await client.send_message(
                    chat_id=chat_id,
                    text=v_text,
                    reply_markup=v_markup,
                    disable_web_page_preview=True
                )
            except Exception:
                pass
        return

    # 2. If no verification is pending (e.g. user already verified or no verification needed):
    if payload:
        try:
            from clone_plugins.commands import start as clone_start
            class PseudoMsg:
                def __init__(self):
                    self.from_user = user
                    self.chat = msg.chat if msg else user
                    self.command = ["start", payload]
                    self.text = f"/start {payload}"
                    self.id = getattr(msg, "id", 0)
                async def reply(self, *args, **kwargs):
                    return await client.send_message(chat_id, *args, **kwargs)
                async def reply_text(self, *args, **kwargs):
                    return await client.send_message(chat_id, *args, **kwargs)
                async def reply_photo(self, *args, **kwargs):
                    return await client.send_photo(chat_id, *args, **kwargs)
            p_msg = PseudoMsg()
            await clone_start(client, p_msg)
            if msg:
                try: await msg.delete()
                except Exception: pass
            return
        except Exception:
            pass

    # 3. Fallback: Show start menu
    try:
        me = getattr(client, "me", None) or (await client.get_me())
        me_mention = me.mention if me else "Bot"
        user_mention = user.mention if user else "User"
        from clone_plugins import script
        from config import BOT_USERNAME, UPDATE_CHANNEL, tg_link

        buttons = [
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"), InlineKeyboardButton("🤖 MY OWN BOT", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
            [InlineKeyboardButton("📢 UPDATE CHANNEL", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))]
        ]
        start_txt = getattr(script, "CLONE_START_TXT", getattr(script, "START_TXT", "Welcome!"))
        try:
            text = start_txt.format(user_mention, me_mention)
        except Exception:
            text = f"Welcome {user_mention} to {me_mention}!"

        if msg and not getattr(msg, "photo", None):
            try:
                return await msg.edit_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
            except Exception:
                pass

        if msg:
            try:
                await msg.delete()
            except Exception:
                pass

        await client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception:
        pass


# ----------------- ADMIN SETTINGS HANDLER ----------------- #

def parse_duration_string(s: str) -> tuple:
    raw = str(s).strip().lower()
    raw = raw.replace("mhont", "month").replace("yaar", "year").replace("yer", "year")
    if "life" in raw:
        return 100 * 365 * 86400, "Lifetime"
    
    m = re.match(r"^(\d+)\s*([a-zA-Z]*)$", raw)
    if m:
        num = int(m.group(1))
        unit = m.group(2).strip()
    else:
        parts = raw.split(maxsplit=1)
        if len(parts) >= 2 and parts[0].isdigit():
            num = int(parts[0])
            unit = parts[1].strip()
        elif len(parts) == 1 and parts[0].isdigit():
            num = int(parts[0])
            unit = "d"
        else:
            return 30 * 86400, "30 day(s)"

    if not unit or unit in ("d", "day", "days"):
        return num * 86400, f"{num} day(s)"
    elif unit in ("s", "sec", "second", "seconds"):
        return max(1, num), f"{num} second(s)"
    elif unit in ("m", "min", "minute", "minutes"):
        return num * 60, f"{num} minute(s)"
    elif unit in ("h", "hr", "hour", "hours"):
        return num * 3600, f"{num} hour(s)"
    elif unit in ("mo", "month", "months"):
        return num * 30 * 86400, f"{num} month(s)"
    elif unit in ("y", "yr", "year", "years"):
        return num * 365 * 86400, f"{num} year(s)"
    else:
        return num * 86400, f"{num} day(s)"

def format_time_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "Expired"
    if seconds < 60:
        return f"{seconds}s Left"
    if seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s Left" if secs else f"{mins}m Left"
    if seconds < 86400:
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hrs}h {mins}m Left" if mins else f"{hrs}h Left"
    days = seconds // 86400
    hrs = (seconds % 86400) // 3600
    return f"{days}d {hrs}h Left" if hrs else f"{days} Day(s) Left"


async def get_bot_send_client(client, target_bid=None):
    """
    Returns (send_client, bot_name, bot_username)
    If target_bid is provided, finds the clone bot Client so notifications originate from that bot.
    """
    send_client = client
    bot_name = ""
    bot_user = ""

    if target_bid:
        try:
            from plugins.clone import get_clone_client, CLONES, mongo_db
            c_client = get_clone_client(target_bid)
            if not c_client:
                for k, v in CLONES.items():
                    if str(k) == str(target_bid):
                        c_client = v
                        break
            if c_client:
                send_client = c_client
                b_info = c_client.me or (await c_client.get_me())
                if b_info:
                    bot_name = b_info.first_name or "Bot"
                    bot_user = f"@{b_info.username}" if b_info.username else ""
            elif mongo_db is not None:
                b_doc = mongo_db.bots.find_one({"bot_id": int(target_bid)})
                if b_doc:
                    bot_name = b_doc.get("name") or b_doc.get("first_name") or "Bot"
                    uname = b_doc.get("username")
                    bot_user = f"@{uname}" if uname else ""
        except Exception:
            pass

    if not bot_name:
        try:
            me = client.me or (await client.get_me())
            if me:
                bot_name = me.first_name or "Bot"
                bot_user = f"@{me.username}" if me.username else ""
        except Exception:
            bot_name = "Bot"

    return send_client, bot_name, bot_user

async def handle_premium_callbacks(client, query, data, user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid=None):
    data_str = str(data or "")
    if not target_bid and ":" in data_str:
        try:
            target_bid = int(data_str.split(":", 1)[1])
        except Exception:
            pass

    # Fallback to active_clone_edit if target_bid is still not resolved
    if not target_bid:
        try:
            from plugins.clone import mongo_db
            if mongo_db is not None:
                act = mongo_db.active_clone_edit.find_one({"user_id": int(user_id)})
                if act and act.get("bot_id"):
                    target_bid = int(act.get("bot_id"))
        except Exception:
            pass

    # If this client is a clone bot, target_bid is client.me.id
    if not target_bid and hasattr(client, "me") and client.me:
        from config import BOT_USERNAME
        if BOT_USERNAME and client.me.username and client.me.username.lower() != BOT_USERNAME.lower():
            target_bid = client.me.id

    # Ensure r and save_fn correctly target the clone bot's record if target_bid is present
    if target_bid:
        try:
            from plugins.clone import mongo_db
            if mongo_db is not None:
                bot_doc = mongo_db.bots.find_one({"bot_id": int(target_bid)})
                if bot_doc:
                    r = bot_doc
                    def _custom_save(**kwargs):
                        mongo_db.bots.update_one({"bot_id": int(target_bid)}, {"$set": kwargs}, upsert=True)
                    save_fn = _custom_save
        except Exception:
            pass

    def cb(name: str) -> str:
        return f"{name}:{target_bid}" if target_bid else name

    is_master = False
    if hasattr(client, "me") and client.me:
        from config import BOT_USERNAME
        if BOT_USERNAME and client.me.username and client.me.username.lower() == BOT_USERNAME.lower():
            is_master = True

    if is_master:
        back_main = f"manage_clone:{target_bid}" if target_bid else "settings_back"
    else:
        back_main = f"manage_clone:{target_bid}" if target_bid else "clone_settings_hub"

    async def clean_show(text, reply_markup=None):
        msg = getattr(query, "message", None) or query
        if msg:
            if getattr(msg, "photo", None) or getattr(msg, "media", None):
                try:
                    return await msg.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    if "MESSAGE_NOT_MODIFIED" in str(e).upper():
                        return msg
                try:
                    await msg.delete()
                except Exception:
                    pass
                return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            else:
                try:
                    return await msg.edit_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                except Exception as e:
                    if "MESSAGE_NOT_MODIFIED" in str(e).upper():
                        return msg
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        return await client.send_message(user_id, text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

    # 1. Main Premium Plan Menu
    if (
        data_str in ("master_premium_plan", "cset_premium_plan")
        or data_str.startswith(("master_premium_plan:", "cset_premium_plan:"))
    ):
        cancel_listeners_fn(user_id)
        prem_on = bool(r.get("premium_is_on", False) or r.get("premium_enabled", False))
        tgl_label = "🔓 PREMIUM IS ON ✅" if prem_on else "🔒 PREMIUM IS OFF ❌"

        text = (
            "💳 <b>PREMIUM PLAN:</b>\n\n"
            "❝ <b>PREMIUM PLAN: A PAID SUBSCRIPTION THAT GIVES USERS AD-FREE ACCESS, "
            "FASTER DOWNLOADS, AND EXCLUSIVE ENTRY TO RESTRICTED FILES OR GROUPS.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 PREMIUM PLAN MESSAGE", callback_data=cb("cset_prem_msg_menu"))],
            [InlineKeyboardButton("➕ ADD PREMIUM USER", callback_data=cb("cset_prem_add_user"))],
            [InlineKeyboardButton("➖ REMOVE PREMIUM USER", callback_data=cb("cset_prem_rem_user"))],
            [InlineKeyboardButton("👥 PREMIUM USERS LIST", callback_data=cb("cset_prem_list_users"))],
            [InlineKeyboardButton(tgl_label, callback_data=cb("cset_prem_tgl"))],
            [InlineKeyboardButton("‹ BACK", callback_data=back_main)]
        ])
        return await clean_show(text, markup)

    # 2. Toggle Premium ON / OFF
    if data_str.startswith("cset_prem_tgl"):
        cur_s = bool(r.get("premium_is_on", False) or r.get("premium_enabled", False))
        new_s = not cur_s
        save_fn(premium_is_on=new_s, premium_enabled=new_s)
        r["premium_is_on"] = new_s
        r["premium_enabled"] = new_s
        try:
            await query.answer(f"Premium is now {'ON ✅' if new_s else 'OFF ❌'}!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 3. Premium Plan Message Submenu
    if data_str.startswith("cset_prem_msg_menu"):
        cancel_listeners_fn(user_id)
        text = (
            "📝 <b>PREMIUM PLAN MESSAGE:</b>\n\n"
            "❝ <b>PREMIUM PLAN MESSAGE: WHEN USER CLICK ON BUY PREMIUM PLAN BUTTON THEN BOT REPLY PREMIUM PLAN MESSAGE. "
            "IN PREMIUM PLAN MESSAGE BOT OWNER CAN SET PREMIUM PLAN MESSAGE TEXT, PICTURE AND BUTTON.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("PREMIUM PLAN TEXT", callback_data=cb("cset_prem_text_menu"))],
            [InlineKeyboardButton("PREMIUM PLAN QR PICTURE", callback_data=cb("cset_prem_pic_menu"))],
            [InlineKeyboardButton("PREMIUM PLAN UPI", callback_data=cb("cset_prem_upi_menu"))],
            [InlineKeyboardButton("SEND SCREENSHOT CONTACT", callback_data=cb("cset_prem_contact_menu"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]
        ])
        return await clean_show(text, markup)

    # 4. Premium Plan Text Submenu
    if data_str.startswith("cset_prem_text_menu"):
        cancel_listeners_fn(user_id)
        p_text = r.get("premium_plan_text") or "{user_mention}\nBuy Movies and Series Premium Now ⚡"
        text = (
            "💳 <b>PREMIUM PLAN TEXT:</b>\n\n"
            f"<b>TEXT -</b> {p_text}\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<b>{user_mention}</b> : <b>USER - NAME</b>\n\n"
            "<b>YOU CAN USE <u>HTML STYLE FORMATTING</u> IN TEXT</b>"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET PREMIUM TEXT", callback_data=cb("cset_prem_set_txt"))],
            [InlineKeyboardButton("REMOVE PREMIUM TEXT", callback_data=cb("cset_prem_rem_txt"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 4.1 Set Premium Text
    if data_str.startswith("cset_prem_set_txt"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_txt_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_text_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME A PREMIUM TEXT.</b>\n\n"
            "<b>AVAILABLE FILLINGS:</b>\n\n"
            "<b>{user_mention}</b> : <b>USER - NAME</b>\n\n"
            "<b>YOU CAN USE <u>HTML STYLE FORMATTING</u> IN TEXT</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _txt_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_text_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            save_fn(premium_plan_text=t)
            r["premium_plan_text"] = t
            clear_user_session(user_id)

            if prompt_msg:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
            try:
                await ans.delete()
            except Exception:
                pass

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_text_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET PREMIUM TEXT -</b>\n\n{t}",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_txt_worker())
        return

    # 4.2 Remove Premium Text
    if data_str.startswith("cset_prem_rem_txt"):
        save_fn(premium_plan_text=None)
        r["premium_plan_text"] = None
        try:
            await query.answer("Premium text removed successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_text_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5. Premium Plan Picture Submenu
    if data_str.startswith("cset_prem_pic_menu"):
        cancel_listeners_fn(user_id)
        has_pic = bool(r.get("premium_plan_photo") or r.get("premium_qr_pic"))
        pic_status = "<b>ALREADY ADDED PICTURE...</b>" if has_pic else "<b>YOU DIDN'T ADD ANY PICTURE...</b>"
        is_spoiler = bool(r.get("premium_spoiler", False))
        is_invert = bool(r.get("premium_invert_cap", False))
        spoiler_txt = "✅" if is_spoiler else "❌"
        invert_txt = "✅" if is_invert else "❌"

        text = (
            "❝ <b>INVERT CAPTION : IF ON THEN CAPTION SHOW ABOVE PREMIUM MESSAGE PICTURE, "
            "IF OFF THEN CAPTION SHOWN BELOW PREMIUM MESSAGE PICTURE AS NORMAL.\n\n"
            "SPOILER ANIMATION : IF ON THEN PREMIUM MESSAGE PICTURE GET SPOILER ANIMATION, "
            "IF OFF THEN NO SPOILER ANIMATION.</b> ❞\n\n"
            f"{pic_status}\n\n"
            f"<b>SPOILER -</b> {spoiler_txt}\n"
            f"<b>INVERT CAPTION -</b> {invert_txt}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET PREMIUM PIC", callback_data=cb("cset_prem_set_pic"))],
            [InlineKeyboardButton("DELETE PREMIUM PIC", callback_data=cb("cset_prem_del_pic"))],
            [InlineKeyboardButton("VIEW PREMIUM PIC", callback_data=cb("cset_prem_view_pic"))],
            [InlineKeyboardButton(f"SPOILER - {spoiler_txt}", callback_data=cb("cset_prem_tgl_spoiler"))],
            [InlineKeyboardButton(f"INVERT CAPTION - {invert_txt}", callback_data=cb("cset_prem_tgl_invert"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 5.1 Set Picture
    if data_str.startswith("cset_prem_set_pic"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_pic_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_pic_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME A PICTURE.</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _pic_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            txt = (ans.text or ans.caption or "").strip()
            if txt.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            photo_id = None
            if ans.photo:
                photo_id = ans.photo.file_id
            elif ans.document and ans.document.mime_type and ans.document.mime_type.startswith("image/"):
                photo_id = ans.document.file_id

            if photo_id:
                local_path = None
                try:
                    from settings_modules.thumbnail import save_thumbnail_media
                    local_path = await save_thumbnail_media(client, ans, user_id, prefix=f"prem_qr_{target_bid or 'master'}")
                except Exception:
                    pass
                upd = {
                    "premium_plan_photo": photo_id,
                    "premium_qr_pic": photo_id
                }
                if local_path:
                    upd["premium_qr_path"] = local_path
                    upd["premium_plan_photo_path"] = local_path
                save_fn(**upd)
                r.update(upd)
                clear_user_session(user_id)

                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                try:
                    await ans.delete()
                except Exception:
                    pass

                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_pic_menu"))]])
                photo_to_send = local_path or photo_id
                try:
                    return await client.send_photo(
                        chat_id=user_id,
                        photo=photo_to_send,
                        caption="<b>SUCCESSFULLY PICTURE SET</b> ✅",
                        reply_markup=back_markup,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    return await client.send_message(
                        chat_id=user_id,
                        text="<b>SUCCESSFULLY PICTURE SET</b> ✅",
                        reply_markup=back_markup,
                        parse_mode=enums.ParseMode.HTML
                    )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid photo picture.</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

        asyncio.create_task(_pic_worker())
        return

    # 5.2 Delete Picture
    if data_str.startswith("cset_prem_del_pic"):
        save_fn(premium_plan_photo=None, premium_qr_pic=None, premium_qr_path=None, premium_plan_photo_path=None)
        r["premium_plan_photo"] = None
        r["premium_qr_pic"] = None
        r["premium_qr_path"] = None
        r["premium_plan_photo_path"] = None
        try:
            await query.answer("Picture deleted successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5.3 View Picture
    if data_str.startswith("cset_prem_view_pic"):
        photo_id = r.get("premium_plan_photo") or r.get("premium_qr_pic")
        if photo_id:
            try:
                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_pic_menu"))]])
                await client.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption="🖼️ <b>YOUR CURRENT PREMIUM QR/PICTURE</b>",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                if query.message:
                    try:
                        await query.message.delete()
                    except Exception:
                        pass
                return
            except Exception:
                pass
        try:
            await query.answer("You haven't set any premium photo yet!", show_alert=True)
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 5.4 Toggle Spoiler & Invert Caption
    if data_str.startswith("cset_prem_tgl_spoiler"):
        new_sp = not bool(r.get("premium_spoiler", False))
        save_fn(premium_spoiler=new_sp)
        r["premium_spoiler"] = new_sp
        try:
            await query.answer(f"Spoiler: {'ON ✅' if new_sp else 'OFF ❌'}")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    if data_str.startswith("cset_prem_tgl_invert"):
        new_inv = not bool(r.get("premium_invert_cap", False))
        save_fn(premium_invert_cap=new_inv)
        r["premium_invert_cap"] = new_inv
        try:
            await query.answer(f"Invert caption: {'ON ✅' if new_inv else 'OFF ❌'}")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_pic_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 6. Premium Plan UPI Submenu
    if data_str.startswith("cset_prem_upi_menu"):
        cancel_listeners_fn(user_id)
        upi_id = r.get("premium_upi_id") or "sonukhatik7193@oksbi"
        text = (
            "💳 <b>PREMIUM PLAN UPI:</b>\n\n"
            f"<b>UPI ID -</b> <code>{upi_id}</code>\n\n"
            "❝ <b>SET YOUR UPI ID (e.g. <code>sonukhatik7193@oksbi</code>). "
            "THIS UPI ID WILL BE DISPLAYED TO USERS IN THE UPI PAYMENT SCREEN WITH A ONE-TAP COPY OPTION.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET UPI ID", callback_data=cb("cset_prem_set_upi"))],
            [InlineKeyboardButton("REMOVE UPI ID", callback_data=cb("cset_prem_rem_upi"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 6.1 Set UPI ID
    if data_str.startswith("cset_prem_set_upi"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_upi_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_upi_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME YOUR UPI ID (e.g. <code>sonukhatik7193@oksbi</code>).</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _upi_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_upi_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            save_fn(premium_upi_id=t)
            r["premium_upi_id"] = t
            clear_user_session(user_id)

            if prompt_msg:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
            try:
                await ans.delete()
            except Exception:
                pass

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_upi_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET UPI ID -</b> <code>{t}</code> ✅",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_upi_worker())
        return

    # 6.2 Remove UPI ID
    if data_str.startswith("cset_prem_rem_upi"):
        save_fn(premium_upi_id=None)
        r["premium_upi_id"] = None
        try:
            await query.answer("UPI ID removed successfully!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_upi_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 7. Send Screenshot Contact Submenu
    if data_str.startswith("cset_prem_contact_menu"):
        cancel_listeners_fn(user_id)
        _, _, display_c = get_contact_info(r)
        text = (
            "📨 <b>SEND SCREENSHOT CONTACT:</b>\n\n"
            f"<b>CONTACT -</b> <code>{display_c}</code>\n\n"
            "❝ <b>SET YOUR TELEGRAM USERNAME OR LINK (e.g. <code>@movies_1780</code> or <code>https://t.me/movies_1780</code>). "
            "WHEN USERS CLICK ON '* SEND PAYMENT SCREENSHOT *', IT WILL DIRECTLY OPEN THIS TELEGRAM ACCOUNT.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("SET CONTACT USERNAME", callback_data=cb("cset_prem_set_contact"))],
            [InlineKeyboardButton("REMOVE CONTACT", callback_data=cb("cset_prem_rem_contact"))],
            [InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_msg_menu"))]
        ])
        return await clean_show(text, markup)

    # 7.1 Set Contact Username / URL
    if data_str.startswith("cset_prem_set_contact"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_contact_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("cset_prem_contact_menu"))]])
        prompt_msg = await clean_show(
            "<b>SEND ME YOUR TELEGRAM USERNAME OR LINK (e.g. <code>@movies_1780</code>).</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _contact_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("cset_prem_contact_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            clean_c = t.lstrip("@").strip()
            save_fn(premium_screenshot_contact=clean_c)
            r["premium_screenshot_contact"] = clean_c
            clear_user_session(user_id)

            if prompt_msg:
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
            try:
                await ans.delete()
            except Exception:
                pass

            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("cset_prem_contact_menu"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"<b>SUCCESSFULLY SET CONTACT -</b> <code>@{clean_c}</code> ✅",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_contact_worker())
        return

    # 7.2 Remove Contact
    if data_str.startswith("cset_prem_rem_contact"):
        save_fn(premium_screenshot_contact=None)
        r["premium_screenshot_contact"] = None
        try:
            await query.answer("Contact reset to default!")
        except Exception:
            pass
        return await handle_premium_callbacks(client, query, cb("cset_prem_contact_menu"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

    # 8. Add Premium User
    if data_str.startswith("cset_prem_add_user"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_add_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("master_premium_plan"))]])
        prompt_msg = await clean_show(
            """➕ <b>ADD PREMIUM USER:</b>

<b>SEND USER ID TO ADD PREMIUM:</b>
(e.g. <code>8378171861</code> or <code>8378171861 1d</code>)

<i>Format: Send User ID first, then send duration (1s, 1m, 1h, 1d, 1 month, 1 year), or send both together!</i>

<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>""",
            prompt_markup
        )

        async def _add_u_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            parts = t.split(maxsplit=1)
            target_uid = None
            duration_str = None

            if len(parts) >= 1 and parts[0].isdigit():
                target_uid = int(parts[0])
                if len(parts) >= 2 and parts[1].strip():
                    duration_str = parts[1].strip()

            if not target_uid:
                try:
                    await ans.reply("⚠️ <b>Please send a valid numeric User ID!</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            # If only User ID was sent, prompt for duration
            if not duration_str:
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass

                step2_token = start_user_session(user_id, f"prem_dur_{target_uid}_{target_bid or 'master'}")
                step2_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("master_premium_plan"))]])
                step2_msg = await clean_show(
                    f"""➕ <b>ADD PREMIUM USER:</b> <code>{target_uid}</code>

<b>NOW SEND PREMIUM DURATION:</b>

• <code>1s</code> : 1 Second
• <code>1m</code> : 1 Minute
• <code>1h</code> : 1 Hour
• <code>1d</code> : 1 Day
• <code>1 month</code> : 1 Month (or <code>1 mhont</code>)
• <code>1 year</code> : 1 Year (or <code>1 yaar</code>)
• <code>30</code> : 30 Days

<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>""",
                    step2_markup
                )

                try:
                    dur_ans = await client.listen(chat_id=user_id, timeout=300)
                except Exception:
                    clear_user_session(user_id)
                    return
                if not is_user_session_active(user_id, step2_token):
                    return

                dur_t = (dur_ans.text or dur_ans.caption or "").strip()
                if dur_t.lower() == "/cancel":
                    try:
                        await dur_ans.delete()
                    except Exception:
                        pass
                    if step2_msg:
                        try:
                            await step2_msg.delete()
                        except Exception:
                            pass
                    clear_user_session(user_id)
                    return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

                duration_str = dur_t
                ans_to_delete = dur_ans
                msg_to_delete = step2_msg
            else:
                ans_to_delete = ans
                msg_to_delete = prompt_msg

            duration_secs, duration_display = parse_duration_string(duration_str)
            now = int(time.time())
            exp_ts = now + duration_secs

            users_list = list(r.get("premium_users", []))
            users_list = [u for u in users_list if int(u.get("user_id", 0)) != target_uid]
            users_list.append({
                "user_id": target_uid,
                "expires_at": exp_ts,
                "added_at": now,
                "duration": duration_display
            })

            save_fn(premium_users=users_list, premium_is_on=True, premium_enabled=True)
            r["premium_users"] = users_list
            r["premium_is_on"] = True
            r["premium_enabled"] = True
            clear_user_session(user_id)

            if msg_to_delete:
                try:
                    await msg_to_delete.delete()
                except Exception:
                    pass
            if ans_to_delete:
                try:
                    await ans_to_delete.delete()
                except Exception:
                    pass

            # Notify target user via the specific bot (clone or master)
            send_client, bot_name, bot_user = await get_bot_send_client(client, target_bid)
            notified = False
            try:
                notify_text = (
                    f"🎉 <b>CONGRATULATIONS! PREMIUM ACTIVATED</b>\n\n"
                    f"👑 <b>You have been granted Premium Access!</b>\n"
                    f"⏳ <b>Duration:</b> <b>{duration_display}</b>\n"
                    f"🤖 <b>Bot:</b> {bot_name} {bot_user}\n\n"
                    f"⚡ <i>Now you can access all files without ads or verification!</i>"
                )
                await send_client.send_message(chat_id=target_uid, text=notify_text, parse_mode=enums.ParseMode.HTML)
                notified = True
            except Exception:
                notified = False

            notify_status = f"\n📩 <i>Notification sent to user via {bot_name}!</i>" if notified else f"\n⚠️ <i>(Note: User hasn't started {bot_name} in PM, so private notification could not be delivered)</i>"
            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
            return await client.send_message(
                chat_id=user_id,
                text=f"✅ <b>User <code>{target_uid}</code> has been added to Premium for {duration_display}!</b>{notify_status}",
                reply_markup=back_markup,
                parse_mode=enums.ParseMode.HTML
            )

        asyncio.create_task(_add_u_worker())
        return

    # 9. Remove Premium User
    if data_str.startswith("cset_prem_rem_user"):
        cancel_listeners_fn(user_id)
        sess_token = start_user_session(user_id, f"prem_rem_{target_bid or 'master'}")
        try:
            await query.answer()
        except Exception:
            pass

        prompt_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data=cb("master_premium_plan"))]])
        prompt_msg = await clean_show(
            "➖ <b>REMOVE PREMIUM USER:</b>\n\n"
            "<b>SEND USER ID TO REMOVE FROM PREMIUM:</b>\n\n"
            "<code>/cancel</code> - <b>CANCEL THIS PROCESS.</b>",
            prompt_markup
        )

        async def _rem_u_worker():
            try:
                ans = await client.listen(chat_id=user_id, timeout=300)
            except Exception:
                clear_user_session(user_id)
                return
            if not is_user_session_active(user_id, sess_token):
                return

            t = (ans.text or ans.caption or "").strip()
            if t.lower() == "/cancel":
                try:
                    await ans.delete()
                except Exception:
                    pass
                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

            if t.isdigit():
                target_uid = int(t)
                users_list = list(r.get("premium_users", []))
                users_list = [u for u in users_list if int(u.get("user_id", 0)) != target_uid]

                save_fn(premium_users=users_list)
                r["premium_users"] = users_list
                clear_user_session(user_id)

                if prompt_msg:
                    try:
                        await prompt_msg.delete()
                    except Exception:
                        pass
                try:
                    await ans.delete()
                except Exception:
                    pass

                # Notify user that premium has ended / removed via the specific bot
                send_client, bot_name, bot_user = await get_bot_send_client(client, target_bid)
                rem_notified = False
                try:
                    rem_notify_text = (
                        f"⚠️ <b>PREMIUM ACCESS ENDED</b>\n\n"
                        f"ℹ️ <b>Your premium subscription for {bot_name} {bot_user} has ended or been removed.</b>\n\n"
                        f"🔐 <i>Now you need to verify or purchase premium to access files.</i>"
                    )
                    await send_client.send_message(chat_id=target_uid, text=rem_notify_text, parse_mode=enums.ParseMode.HTML)
                    rem_notified = True
                except Exception:
                    rem_notified = False

                rem_status = f"\n📩 <i>Notification sent to user via {bot_name}!</i>" if rem_notified else f"\n⚠️ <i>(User has not started {bot_name} in PM)</i>"
                back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
                return await client.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>User <code>{target_uid}</code> removed from Premium!</b>{rem_status}",
                    reply_markup=back_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                try:
                    await ans.reply("⚠️ <b>Please send a valid numeric USER ID.</b>")
                except Exception:
                    pass
                clear_user_session(user_id)
                return await handle_premium_callbacks(client, query, cb("master_premium_plan"), user_id, r, save_fn, cancel_listeners_fn, edit_or_reply_fn, target_bid)

        asyncio.create_task(_rem_u_worker())
        return

    # 10. List Premium Users
    if data_str.startswith("cset_prem_list_users"):
        cancel_listeners_fn(user_id)
        users_list = list(r.get("premium_users", []))
        now = int(time.time())
        active_users = [u for u in users_list if int(u.get("expires_at", 0)) > now]

        if not active_users:
            text = (
                "👥 <b>PREMIUM USERS LIST:</b>\n\n"
                "<i>No active premium users found.</i>"
            )
        else:
            lines = ["👥 <b>PREMIUM USERS LIST:</b>\n", f"<b>Total Active Users:</b> <b>{len(active_users)}</b>\n"]
            for idx, u in enumerate(active_users, 1):
                uid = u.get("user_id")
                exp = int(u.get("expires_at", 0))
                time_left_str = format_time_remaining(exp - now)
                lines.append(f"{idx}. <code>{uid}</code> — <b>{time_left_str}</b>")
            text = "\n".join(lines)

        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=cb("master_premium_plan"))]])
        return await clean_show(text, markup)



_expiry_checker_started = False

def start_premium_expiry_checker(main_bot=None):
    global _expiry_checker_started
    if _expiry_checker_started:
        return
    _expiry_checker_started = True

    async def _expiry_loop():
        while True:
            try:
                now = int(time.time())
                from plugins.clone import mongo_db, get_clone_client
                if mongo_db is not None:
                    # 1. Check all clone bots in mongo_db.bots
                    bots_cursor = mongo_db.bots.find({"premium_users": {"$exists": True, "$ne": []}})
                    for b_doc in list(bots_cursor):
                        bid = b_doc.get("bot_id")
                        if not bid:
                            continue
                        prem_users = b_doc.get("premium_users") or []
                        expired_users = []
                        remaining_users = []
                        for pu in prem_users:
                            try:
                                exp = int(pu.get("expires_at", 0))
                                if exp > 0 and exp <= now:
                                    expired_users.append(pu)
                                else:
                                    remaining_users.append(pu)
                            except Exception:
                                remaining_users.append(pu)

                        if expired_users:
                            mongo_db.bots.update_one(
                                {"bot_id": int(bid)},
                                {"$set": {"premium_users": remaining_users}}
                            )
                            c_client = get_clone_client(bid)
                            if c_client:
                                b_info = c_client.me or (await c_client.get_me())
                                bot_name = b_info.first_name if b_info else "Bot"
                                bot_user = f"@{b_info.username}" if (b_info and b_info.username) else ""
                                for exp_u in expired_users:
                                    uid = exp_u.get("user_id")
                                    try:
                                        exp_text = (
                                            f"⚠️ <b>YOUR PREMIUM HAS EXPIRED!</b>\n\n"
                                            f"ℹ️ <b>Your premium subscription for {bot_name} {bot_user} has expired.</b>\n\n"
                                            f"🔐 <i>Now you need to verify or purchase premium to access files.</i>"
                                        )
                                        await c_client.send_message(chat_id=int(uid), text=exp_text, parse_mode=enums.ParseMode.HTML)
                                    except Exception:
                                        pass

                    # 2. Check master_settings for master bot premium users
                    m_rec = mongo_db.master_settings.find_one({"type": "master_config"}) or mongo_db.master_settings.find_one({}) or {}
                    if m_rec:
                        prem_users = m_rec.get("premium_users") or []
                        expired_users = []
                        remaining_users = []
                        for pu in prem_users:
                            try:
                                exp = int(pu.get("expires_at", 0))
                                if exp > 0 and exp <= now:
                                    expired_users.append(pu)
                                else:
                                    remaining_users.append(pu)
                            except Exception:
                                remaining_users.append(pu)

                        if expired_users:
                            mongo_db.master_settings.update_one(
                                {"type": "master_config"},
                                {"$set": {"premium_users": remaining_users}}
                            )
                            mb = main_bot
                            if not mb:
                                try:
                                    from bot import StreamBot
                                    mb = StreamBot
                                except Exception:
                                    pass
                            if mb and getattr(mb, "is_connected", False):
                                b_info = mb.me or (await mb.get_me())
                                bot_name = b_info.first_name if b_info else "Bot"
                                bot_user = f"@{b_info.username}" if (b_info and b_info.username) else ""
                                for exp_u in expired_users:
                                    uid = exp_u.get("user_id")
                                    try:
                                        exp_text = (
                                            f"⚠️ <b>YOUR PREMIUM HAS EXPIRED!</b>\n\n"
                                            f"ℹ️ <b>Your premium subscription for {bot_name} {bot_user} has expired.</b>\n\n"
                                            f"🔐 <i>Now you need to verify or purchase premium to access files.</i>"
                                        )
                                        await mb.send_message(chat_id=int(uid), text=exp_text, parse_mode=enums.ParseMode.HTML)
                                    except Exception:
                                        pass
            except Exception:
                pass
            await asyncio.sleep(15)

    asyncio.create_task(_expiry_loop())
