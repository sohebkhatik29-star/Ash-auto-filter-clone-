import asyncio
import datetime
import re
import secrets
import time
from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins.users_api import get_user, get_short_link
from plugins.clone import mongo_db
from config import ADMINS, PUBLIC_FILE_STORE

MAX_FILES = 5000
_SPL_LOCKS = {}
_SPL_SESSIONS = {}  # (bot_id, user_id) -> session dict
_SPL_WAIT_INPUT = {}  # (bot_id, user_id) -> state dict ("modify", "delete", "add_content")

LINK_REGEX = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:[a-zA-Z0-9_]+)\?start=(?:spl_|special_)?([a-zA-Z0-9_-]+)")


def _lock(client, user_id):
    key = (int(client.me.id), int(user_id))
    if key not in _SPL_LOCKS:
        _SPL_LOCKS[key] = asyncio.Lock()
    return _SPL_LOCKS[key]


def is_special_link_active(bot_id: int, user_id: int) -> bool:
    key = (int(bot_id), int(user_id))
    return key in _SPL_SESSIONS or key in _SPL_WAIT_INPUT


def is_allowed_special(client, user_id: int) -> bool:
    if PUBLIC_FILE_STORE:
        return True
    try:
        if int(user_id) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    if cmd.is_owner_or_mod(client, user_id):
        return True
    return cmd.bot_record(client).get("mode") == "public"


# --- Menu Markup ---
def _main_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("CREATE", callback_data="spl_create"),
            InlineKeyboardButton("MODIFY", callback_data="spl_modify"),
        ],
        [
            InlineKeyboardButton("DELETE", callback_data="spl_delete"),
            InlineKeyboardButton("CLOSE", callback_data="spl_close"),
        ],
    ])


def _session_controls(token, paused=False):
    pause_btn = InlineKeyboardButton("RESUME", callback_data=f"spl_resume_{token}") if paused else InlineKeyboardButton("PAUSE", callback_data=f"spl_pause_{token}")
    return InlineKeyboardMarkup([
        [pause_btn],
        [InlineKeyboardButton("GENERATE LINK", callback_data=f"spl_gen_{token}")],
        [InlineKeyboardButton("CANCEL", callback_data=f"spl_cancel_{token}")],
    ])


def _link_done_markup(token, share_url):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("MODIFY LINK", callback_data=f"spl_panel_{token}")],
        [InlineKeyboardButton("📢 SHARE URL", url=share_url)],
    ])


def _customize_panel_markup(token):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("EDIT CONTENTS", callback_data=f"spl_edit_{token}"),
            InlineKeyboardButton("WHITELISTERS", callback_data=f"spl_white_{token}"),
        ],
        [
            InlineKeyboardButton("PROTECT CONTENT", callback_data=f"spl_protect_{token}"),
            InlineKeyboardButton("AUTO EXPIRE", callback_data=f"spl_expire_{token}"),
        ],
        [
            InlineKeyboardButton("GET LINK", callback_data=f"spl_getlink_{token}"),
            InlineKeyboardButton("DELETE", callback_data=f"spl_delconfirm_{token}"),
        ],
    ])


# --- Main Command Handler ---
async def special_link_cmd(client, message):
    if not is_allowed_special(client, message.from_user.id):
        return await message.reply("❌ Special link generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    # Clear any pending state
    key = (int(client.me.id), int(message.from_user.id))
    _SPL_SESSIONS.pop(key, None)
    _SPL_WAIT_INPUT.pop(key, None)

    text = (
        "Do you want to create a new special link, or modify an existing one, or delete it?\n\n"
        "<u>To know more click here</u>"
    )
    await message.reply(text, reply_markup=_main_menu_markup())
    raise StopPropagation


# --- Capture Incoming Files / Forwarded Files ---
async def capture_special_message(client, message):
    if mongo_db is None or not message.from_user or not message.chat or message.chat.type.value != "private":
        return

    key = (int(client.me.id), int(message.from_user.id))

    # 1. Check if waiting for link input for modify or delete
    wait_state = _SPL_WAIT_INPUT.get(key)
    if wait_state:
        # Check cancel
        if message.text and message.text.strip().lower() == "/cancel":
            _SPL_WAIT_INPUT.pop(key, None)
            await message.reply("Cancelled.")
            raise StopPropagation

        mode = wait_state.get("mode")
        if mode in ("modify", "delete"):
            text = (message.text or "").strip()
            match = LINK_REGEX.search(text)
            token = match.group(1) if match else text
            record = mongo_db.special_links.find_one({"bot_id": client.me.id, "token": token})
            if not record:
                # Try finding by start parameter directly
                record = mongo_db.special_links.find_one({"bot_id": client.me.id, "$or": [{"token": token}, {"short_token": token}]})

            if not record:
                await message.reply("Invalid Link")
                raise StopPropagation

            _SPL_WAIT_INPUT.pop(key, None)
            if mode == "modify":
                date_str = datetime.date.fromtimestamp(record.get("created_at", time.time())).strftime("%Y-%m-%d")
                count = len(record.get("messages", []))
                panel_text = (
                    f"Customize this link using the options below.\n\n"
                    f"- message's count: {count}\n"
                    f"- created on: {date_str}\n\n"
                    f"<u>To know more click here</u>"
                )
                await message.reply(panel_text, reply_markup=_customize_panel_markup(record["token"]))
            elif mode == "delete":
                mongo_db.special_links.delete_one({"_id": record["_id"]})
                await message.reply("✅ Special link has been deleted permanently.")
            raise StopPropagation

        elif mode == "add_content":
            if message.text and message.text.startswith("/"):
                _SPL_WAIT_INPUT.pop(key, None)
                return
            token = wait_state.get("token")
            record = mongo_db.special_links.find_one({"bot_id": client.me.id, "token": token})
            if not record:
                _SPL_WAIT_INPUT.pop(key, None)
                await message.reply("❌ Special link record not found.")
                raise StopPropagation

            messages = list(record.get("messages", []))
            item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
            messages.append(item)
            mongo_db.special_links.update_one({"_id": record["_id"]}, {"$set": {"messages": messages}})
            await message.reply(f"✅ Added to special link! Total messages: {len(messages)}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ BACK TO SETTINGS", callback_data=f"spl_panel_{token}")]
            ]))
            raise StopPropagation

    # 2. Check active creation session
    session = _SPL_SESSIONS.get(key)
    if not session:
        return

    if message.text and message.text.startswith("/"):
        if message.text.strip().lower() == "/cancel":
            _SPL_SESSIONS.pop(key, None)
            await message.reply("❌ Special link creation cancelled.")
            raise StopPropagation
        return

    if session.get("paused"):
        await message.reply("⚠️ Session is currently paused. Tap RESUME on the control panel to add more messages.")
        raise StopPropagation

    async with _lock(client, message.from_user.id):
        messages = session.get("messages", [])
        if len(messages) >= MAX_FILES:
            raise StopPropagation

        item = {"chat_id": int(message.chat.id), "message_id": int(message.id)}
        messages.append(item)
        session["messages"] = messages
        count = len(messages)

        # Update or send control panel
        text = f"Stored Messages: {count}\n\nWant to add another message? Just send it!"
        markup = _session_controls(session["session_id"], paused=False)

        ctrl_msg_id = session.get("control_msg_id")
        now = time.time()
        last_panel_time = session.get("last_panel_time", 0)

        # Smooth update: if panel exists and not flooded, edit; otherwise send fresh panel below
        if ctrl_msg_id and (now - last_panel_time < 2.0 or count % 5 != 0):
            try:
                await client.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=ctrl_msg_id,
                    text=text,
                    reply_markup=markup,
                )
                session["last_panel_time"] = now
                raise StopPropagation
            except Exception:
                pass

        try:
            if ctrl_msg_id:
                try:
                    await client.delete_messages(message.chat.id, ctrl_msg_id)
                except Exception:
                    pass
            sent = await message.reply(text, reply_markup=markup)
            session["control_msg_id"] = sent.id
            session["last_panel_time"] = now
        except Exception:
            pass

    raise StopPropagation


# --- Callback Handler ---
async def special_link_callbacks(client, query):
    data = query.data or ""
    if not data.startswith("spl_"):
        return

    if mongo_db is None:
        return await query.answer("Database is not configured.", show_alert=True)

    key = (int(client.me.id), int(query.from_user.id))

    # 1. Main Menu Callbacks
    if data == "spl_create":
        session_id = secrets.token_urlsafe(10)
        _SPL_SESSIONS[key] = {
            "session_id": session_id,
            "messages": [],
            "paused": False,
            "control_msg_id": None,
            "last_panel_time": time.time(),
        }
        _SPL_WAIT_INPUT.pop(key, None)
        try:
            await query.message.edit_text("Send me the message you want to store")
        except Exception:
            await query.message.reply("Send me the message you want to store")
        return await query.answer()

    elif data == "spl_modify":
        _SPL_WAIT_INPUT[key] = {"mode": "modify"}
        _SPL_SESSIONS.pop(key, None)
        try:
            await query.message.edit_text("Send Your Special Link For Modify")
        except Exception:
            await query.message.reply("Send Your Special Link For Modify")
        return await query.answer()

    elif data == "spl_delete":
        _SPL_WAIT_INPUT[key] = {"mode": "delete"}
        _SPL_SESSIONS.pop(key, None)
        prompt = (
            "please send the special link you want to delete permanently\n\n"
            "Note: Once it is deleted, it cannot be recovered"
        )
        try:
            await query.message.edit_text(prompt)
        except Exception:
            await query.message.reply(prompt)
        return await query.answer()

    elif data == "spl_close":
        _SPL_SESSIONS.pop(key, None)
        _SPL_WAIT_INPUT.pop(key, None)
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.answer("Closed.")

    # 2. Creation Session Callbacks
    if data.startswith("spl_pause_"):
        session = _SPL_SESSIONS.get(key)
        if session:
            session["paused"] = True
            count = len(session.get("messages", []))
            await query.message.edit_text(
                f"Stored Messages: {count}\n\n⏸️ <b>Session Paused.</b>",
                reply_markup=_session_controls(session["session_id"], paused=True)
            )
            return await query.answer("Paused.")
        return await query.answer("Session expired.", show_alert=True)

    elif data.startswith("spl_resume_"):
        session = _SPL_SESSIONS.get(key)
        if session:
            session["paused"] = False
            count = len(session.get("messages", []))
            await query.message.edit_text(
                f"Stored Messages: {count}\n\nWant to add another message? Just send it!",
                reply_markup=_session_controls(session["session_id"], paused=False)
            )
            return await query.answer("Resumed.")
        return await query.answer("Session expired.", show_alert=True)

    elif data.startswith("spl_cancel_"):
        _SPL_SESSIONS.pop(key, None)
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.reply("❌ Special link creation cancelled.")
        return await query.answer("Cancelled.")

    elif data.startswith("spl_gen_"):
        session = _SPL_SESSIONS.pop(key, None)
        if not session or not session.get("messages"):
            return await query.answer("Please send or forward at least one message first.", show_alert=True)

        token = secrets.token_urlsafe(18)
        rec = cmd.bot_record(client)
        protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

        doc = {
            "token": token,
            "bot_id": client.me.id,
            "owner_id": int(query.from_user.id),
            "messages": session["messages"],
            "protected": protected,
            "whitelisters_enabled": False,
            "whitelisters": [],
            "expire_at": None,
            "created_at": int(time.time()),
        }
        mongo_db.special_links.insert_one(doc)

        username = (await client.get_me()).username
        orig_link = f"https://t.me/{username}?start=special_{token}"
        owner = cmd.owner_id(client) or int(query.from_user.id)
        try:
            shown_link = await get_short_link(await get_user(owner), orig_link)
        except Exception:
            shown_link = orig_link

        text = f"Here is your special link:\n\n{shown_link}"
        await query.message.edit_text(
            text,
            reply_markup=_link_done_markup(token, shown_link),
            disable_web_page_preview=True
        )
        return await query.answer("Special link created!")

    # 3. Customization & Settings Callbacks
    parts = data.split("_", 2)
    if len(parts) < 3:
        return

    action, token = parts[1], parts[2]
    record = mongo_db.special_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        return await query.answer("Special link not found or expired.", show_alert=True)

    if action == "panel":
        _SPL_WAIT_INPUT.pop(key, None)
        date_str = datetime.date.fromtimestamp(record.get("created_at", time.time())).strftime("%Y-%m-%d")
        count = len(record.get("messages", []))
        panel_text = (
            f"Customize this link using the options below.\n\n"
            f"- message's count: {count}\n"
            f"- created on: {date_str}\n\n"
            f"<u>To know more click here</u>"
        )
        await query.message.edit_text(panel_text, reply_markup=_customize_panel_markup(token))
        return await query.answer()

    elif action == "edit":
        text = "You can add message or remove a message from this link content"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Add", callback_data=f"spl_add_{token}"),
                InlineKeyboardButton("Remove", callback_data=f"spl_rem_{token}"),
            ],
            [InlineKeyboardButton("back", callback_data=f"spl_panel_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    elif action == "add":
        _SPL_WAIT_INPUT[key] = {"mode": "add_content", "token": token}
        await query.message.edit_text(
            "Send me the message/file you want to add to this link.\n\n/cancel - abort.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("back", callback_data=f"spl_panel_{token}")]])
        )
        return await query.answer()

    elif action == "rem":
        msgs = list(record.get("messages", []))
        if not msgs:
            return await query.answer("No messages left in this link.", show_alert=True)
        msgs.pop()  # Remove last message
        mongo_db.special_links.update_one({"_id": record["_id"]}, {"$set": {"messages": msgs}})
        await query.answer("Last message removed.", show_alert=True)
        # Refresh edit view
        text = f"You can add message or remove a message from this link content\n\nRemaining messages: {len(msgs)}"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Add", callback_data=f"spl_add_{token}"),
                InlineKeyboardButton("Remove", callback_data=f"spl_rem_{token}"),
            ],
            [InlineKeyboardButton("back", callback_data=f"spl_panel_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return

    elif action == "white":
        is_on = record.get("whitelisters_enabled", False)
        status_btn = InlineKeyboardButton("Enable ✅" if not is_on else "Disable ❌", callback_data=f"spl_twhite_{token}")
        text = (
            "Whitelisters Mode\n\n"
            "Limit access to this link to specific users called whitelisters. When enabled, only the users you add as whitelisters can open this link.\n\n"
            "conditions:\n"
            "- if enabled and no whitelisters added, then only moderators can access this link.\n"
            "- if enabled, link will be also accessible for clone whitelisted users.\n"
            "- you can add an unlimited number of whitelister to this link."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("back", callback_data=f"spl_panel_{token}"), status_btn],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    elif action == "twhite":
        new_val = not record.get("whitelisters_enabled", False)
        mongo_db.special_links.update_one({"_id": record["_id"]}, {"$set": {"whitelisters_enabled": new_val}})
        status_btn = InlineKeyboardButton("Enable ✅" if not new_val else "Disable ❌", callback_data=f"spl_twhite_{token}")
        text = (
            "Whitelisters Mode\n\n"
            "Limit access to this link to specific users called whitelisters. When enabled, only the users you add as whitelisters can open this link.\n\n"
            "conditions:\n"
            "- if enabled and no whitelisters added, then only moderators can access this link.\n"
            "- if enabled, link will be also accessible for clone whitelisted users.\n"
            "- you can add an unlimited number of whitelister to this link."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("back", callback_data=f"spl_panel_{token}"), status_btn],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer(f"Whitelisters {'enabled' if new_val else 'disabled'}.")

    elif action == "protect":
        is_on = record.get("protected", False)
        status_btn = InlineKeyboardButton("Enable ✅" if not is_on else "Disable ❌", callback_data=f"spl_tprot_{token}")
        text = (
            "Protect Content\n\n"
            "Protect your content in the link from being forwarded or captured via screenshots by users.\n\n"
            "Note: Even if you disable this feature, if \"No Forward\" is enabled in the clone, that setting will override this one."
        )
        markup = InlineKeyboardMarkup([
            [status_btn],
            [InlineKeyboardButton("Back", callback_data=f"spl_panel_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    elif action == "tprot":
        new_val = not record.get("protected", False)
        mongo_db.special_links.update_one({"_id": record["_id"]}, {"$set": {"protected": new_val}})
        status_btn = InlineKeyboardButton("Enable ✅" if not new_val else "Disable ❌", callback_data=f"spl_tprot_{token}")
        text = (
            "Protect Content\n\n"
            "Protect your content in the link from being forwarded or captured via screenshots by users.\n\n"
            "Note: Even if you disable this feature, if \"No Forward\" is enabled in the clone, that setting will override this one."
        )
        markup = InlineKeyboardMarkup([
            [status_btn],
            [InlineKeyboardButton("Back", callback_data=f"spl_panel_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer(f"Protect content {'enabled' if new_val else 'disabled'}.")

    elif action == "expire":
        exp = record.get("expire_at")
        if exp and exp > time.time():
            rem_min = int((exp - time.time()) / 60)
            status_str = f"Expires in {rem_min} min"
        else:
            status_str = "Lifetime access"

        text = (
            "Auto Expire\n\n"
            "you can set an expiry time so the link deletes itself after a certain period. Once its gone, Nobody can access it (Including you)\n\n"
            f"- Status: {status_str}"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Set", callback_data=f"spl_setexp_{token}"),
                InlineKeyboardButton("remove", callback_data=f"spl_remexp_{token}"),
            ],
            [InlineKeyboardButton("back", callback_data=f"spl_panel_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    elif action == "setexp":
        text = "Select Expiration Duration:"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("10 Minutes", callback_data=f"spl_exptime_{token}_600"),
                InlineKeyboardButton("30 Minutes", callback_data=f"spl_exptime_{token}_1800"),
            ],
            [
                InlineKeyboardButton("1 Hour", callback_data=f"spl_exptime_{token}_3600"),
                InlineKeyboardButton("6 Hours", callback_data=f"spl_exptime_{token}_21600"),
            ],
            [
                InlineKeyboardButton("24 Hours", callback_data=f"spl_exptime_{token}_86400"),
                InlineKeyboardButton("7 Days", callback_data=f"spl_exptime_{token}_604800"),
            ],
            [InlineKeyboardButton("back", callback_data=f"spl_expire_{token}")],
        ])
        await query.message.edit_text(text, reply_markup=markup)
        return await query.answer()

    elif action == "exptime":
        subparts = token.split("_")
        real_token, sec_str = subparts[0], subparts[1]
        seconds = int(sec_str)
        exp_time = int(time.time()) + seconds
        mongo_db.special_links.update_one({"bot_id": client.me.id, "token": real_token}, {"$set": {"expire_at": exp_time}})
        await query.answer("Expiry time set!", show_alert=True)
        # Return to panel
        return await special_link_callbacks(client, type("Q", (), {"data": f"spl_expire_{real_token}", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    elif action == "remexp":
        mongo_db.special_links.update_one({"_id": record["_id"]}, {"$set": {"expire_at": None}})
        await query.answer("Expiry removed (Lifetime access).", show_alert=True)
        return await special_link_callbacks(client, type("Q", (), {"data": f"spl_expire_{token}", "from_user": query.from_user, "message": query.message, "answer": query.answer})())

    elif action == "getlink":
        username = (await client.get_me()).username
        orig_link = f"https://t.me/{username}?start=special_{token}"
        owner = cmd.owner_id(client) or int(query.from_user.id)
        try:
            shown_link = await get_short_link(await get_user(owner), orig_link)
        except Exception:
            shown_link = orig_link

        text = f"Here is your special link:\n\n{shown_link}"
        await query.message.edit_text(
            text,
            reply_markup=_link_done_markup(token, shown_link),
            disable_web_page_preview=True
        )
        return await query.answer()

    elif action == "delconfirm":
        mongo_db.special_links.delete_one({"_id": record["_id"]})
        await query.message.edit_text("✅ Special link deleted permanently.")
        return await query.answer("Link deleted.")


# --- Link Delivery on /start special_<token> ---
async def special_link_start(client, message):
    if len(message.command) != 2:
        return
    payload = message.command[1]
    if not (payload.startswith("special_") or payload.startswith("spl_")):
        return

    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    token = payload.split("_", 1)[1]
    record = mongo_db.special_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        record = mongo_db.special_links.find_one({"bot_id": client.me.id, "$or": [{"token": token}, {"short_token": token}]})

    if not record:
        await message.reply("❌ Invalid or expired special link.")
        raise StopPropagation

    # 1. Check Expiry
    exp = record.get("expire_at")
    if exp and time.time() > exp:
        await message.reply("❌ This special link has expired and is no longer available.")
        raise StopPropagation

    # 2. Check Whitelisters
    if record.get("whitelisters_enabled", False):
        user_id = int(message.from_user.id)
        whitelisters = record.get("whitelisters", [])
        is_mod = cmd.is_owner_or_mod(client, user_id)
        if user_id not in whitelisters and not is_mod:
            await message.reply("❌ You are not authorized to view this special link.")
            raise StopPropagation

    # 3. Check Verification & Force Sub
    access = await cmd.access_verification(client, message.from_user.id, payload)
    if access:
        await message.reply("<b>🔐 Please verify first to access this link.</b>", reply_markup=access)
        raise StopPropagation
    force = await cmd.force_markup(client, message.from_user.id, payload)
    if force:
        await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=force)
        raise StopPropagation

    messages = list(record.get("messages", []))
    if not messages:
        await message.reply("❌ This special link contains no messages.")
        raise StopPropagation

    protected = bool(record.get("protected", False)) or bool(cmd.bot_record(client).get("protect_content", False)) or bool(cmd.bot_record(client).get("no_forward", False))

    for item in messages:
        try:
            await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=int(item["chat_id"]),
                message_id=int(item["message_id"]),
                protect_content=protected,
            )
            await asyncio.sleep(0.08)
        except Exception:
            continue

    raise StopPropagation


def register(client, base_group=-103):
    private = filters.private
    client.add_handler(MessageHandler(special_link_start, filters.command("start") & private), group=base_group)
    client.add_handler(MessageHandler(special_link_cmd, filters.command("special_link") & private), group=base_group)
    client.add_handler(MessageHandler(capture_special_message, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(special_link_callbacks, filters.regex(r"^spl_")), group=base_group)
    return client
