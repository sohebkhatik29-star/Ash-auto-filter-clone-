"""Channel Batch link generator and delivery handler.
Main command: /batch
"""
import asyncio
import re
import secrets
import time
from pyrogram import filters, StopPropagation, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins import commands as cmd
from clone_plugins.users_api import get_user, get_short_link, format_caption
from plugins.clone import mongo_db
from config import PUBLIC_FILE_STORE, ADMINS

_CHANNEL_BATCH_SESSIONS = {}
_ACTIVE_DELIVERIES = {}

LINK_REGEX = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([a-zA-Z0-9_]+)/(\d+)")


def is_channel_batch_active(bot_id: int, user_id: int) -> bool:
    return (int(bot_id), int(user_id)) in _CHANNEL_BATCH_SESSIONS


def is_allowed_batch(client, user_id: int) -> bool:
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


def _extract_chat_and_msg_id(message):
    # 1. Forward tag
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
        if chat_id and msg_id:
            return chat_id, int(msg_id)

    # 2. Text message link
    text = (message.text or message.caption or "").strip()
    if text:
        match = LINK_REGEX.search(text)
        if match:
            chat_str = match.group(1)
            msg_id = int(match.group(2))
            if chat_str.isdigit() or (chat_str.startswith("-") and chat_str[1:].isdigit()):
                chat_id = int(chat_str)
                if not str(chat_id).startswith("-100"):
                    chat_id = int(f"-100{abs(chat_id)}")
            else:
                chat_id = chat_str
            return chat_id, msg_id

    return None, None


async def start_batch(client, message):
    if not is_allowed_batch(client, message.from_user.id):
        return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    if mongo_db is None:
        return await message.reply("❌ Database is not configured.")

    key = (int(client.me.id), int(message.from_user.id))
    _CHANNEL_BATCH_SESSIONS[key] = {
        "step": "first",
        "first_chat_id": None,
        "first_msg_id": None,
        "last_msg_id": None,
        "created_at": time.time(),
    }

    await message.reply(
        "Forward The Batch First Message From your Batch Channel (With Forward Tag)..\n"
        "or Give Me Batch first message link from your batch channel\n\n"
        "<i>Send /cancel to cancel.</i>"
    )
    raise StopPropagation


async def capture_batch_step(client, message):
    if not message.from_user or not message.chat or message.chat.type.value != "private":
        return
    key = (int(client.me.id), int(message.from_user.id))
    session = _CHANNEL_BATCH_SESSIONS.get(key)
    if not session:
        return

    # Check for cancel
    if message.text and message.text.strip().lower() == "/cancel":
        _CHANNEL_BATCH_SESSIONS.pop(key, None)
        await message.reply("❌ Batch creation cancelled.")
        raise StopPropagation

    if message.text and message.text.startswith("/") and not message.text.startswith("http"):
        # Another command sent
        _CHANNEL_BATCH_SESSIONS.pop(key, None)
        return

    step = session.get("step")

    if step == "first":
        chat_id, msg_id = _extract_chat_and_msg_id(message)
        if not chat_id or not msg_id:
            await message.reply(
                "❌ <b>Invalid message or link!</b>\n\n"
                "Please forward the <b>first message</b> with forward tag, or send its direct link.\n"
                "/cancel - to abort."
            )
            raise StopPropagation

        # Check bot admin permissions in the channel
        try:
            chat_obj = await client.get_chat(chat_id)
            chat_id = chat_obj.id
            bot_member = await client.get_chat_member(chat_id, client.me.id)
            # Must have admin status or channel must be accessible
            if str(bot_member.status).lower().endswith(("left", "banned", "kicked")):
                raise PermissionError("Not a member")
        except Exception:
            await message.reply(
                "❌ <b>Bot is not an Admin in that channel!</b>\n\n"
                "Please add me as an <b>Admin</b> in your channel with post/view message rights, then try again.\n"
                "/cancel - to abort."
            )
            raise StopPropagation

        session["first_chat_id"] = chat_id
        session["first_msg_id"] = msg_id
        session["step"] = "last"

        await message.reply(
            "Forward The Batch Last Message From Your Batch Channel (With Forward Tag)..\n"
            "or Give Me Batch last message link from your batch channel\n\n"
            "<i>Send /cancel to cancel.</i>"
        )
        raise StopPropagation

    elif step == "last":
        chat_id, msg_id = _extract_chat_and_msg_id(message)
        if not chat_id or not msg_id:
            await message.reply(
                "❌ <b>Invalid message or link!</b>\n\n"
                "Please forward the <b>last message</b> with forward tag, or send its direct link.\n"
                "/cancel - to abort."
            )
            raise StopPropagation

        first_chat_id = session.get("first_chat_id")
        first_msg_id = session.get("first_msg_id")

        try:
            chat_obj = await client.get_chat(chat_id)
            chat_id = chat_obj.id
        except Exception:
            pass

        if chat_id != first_chat_id:
            await message.reply(
                "❌ <b>Channel mismatch!</b>\n\n"
                "Both first and last messages must be from the <b>same channel</b>.\n"
                "Please send the last message from the same channel, or use /cancel."
            )
            raise StopPropagation

        _CHANNEL_BATCH_SESSIONS.pop(key, None)

        # Normalize start and end
        f_id = min(first_msg_id, msg_id)
        l_id = max(first_msg_id, msg_id)
        total_msgs = (l_id - f_id) + 1

        notice_msg = await message.reply("process time depends upon number of messages")

        status_msg = await message.reply(
            f"Generating Shareable Link...\n\n"
            f"➤ Total Messages: {total_msgs}\n"
            f"➤ Completed: 0\n"
            f"➤ Remaining: {total_msgs}"
        )

        valid_count = 0
        last_edit_time = time.time()

        for idx, cur_id in enumerate(range(f_id, l_id + 1), start=1):
            valid_count += 1
            if time.time() - last_edit_time > 2.0 or idx == total_msgs:
                try:
                    await status_msg.edit_text(
                        f"Generating Shareable Link...\n\n"
                        f"➤ Total Messages: {total_msgs}\n"
                        f"➤ Completed: {idx}\n"
                        f"➤ Remaining: {total_msgs - idx}"
                    )
                    last_edit_time = time.time()
                except Exception:
                    pass

        # Save to database
        token = secrets.token_urlsafe(18)
        rec = cmd.bot_record(client)
        protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

        mongo_db.channel_batch_links.insert_one({
            "token": token,
            "bot_id": client.me.id,
            "owner_id": int(message.from_user.id),
            "channel_id": first_chat_id,
            "first_msg_id": f_id,
            "last_msg_id": l_id,
            "total_messages": total_msgs,
            "protected": protected,
            "created_at": int(time.time()),
        })

        username = (await client.get_me()).username
        orig_link = f"https://t.me/{username}?start=cbatch_{token}"
        shown_link = orig_link

        try:
            await notice_msg.delete()
        except Exception:
            pass

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 SHARE URL", url=f"https://t.me/share/url?url={shown_link}")]
        ])

        await status_msg.edit_text(
            f"Here is your link:\n\n{shown_link}",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
        log_ch = rec.get("log_channel")
        if log_ch:
            try:
                await client.send_message(
                    chat_id=int(log_ch),
                    text=f"📦 <b>NEW BATCH LINK GENERATED:</b>\n\n👤 <b>By:</b> {message.from_user.mention}\n📊 <b>Total Messages:</b> {total_msgs}\n🔗 {shown_link}",
                    disable_web_page_preview=True
                )
            except Exception:
                pass
        raise StopPropagation


async def batch_start_deliver(client, message):
    if len(message.command) != 2 or not message.command[1].startswith("cbatch_"):
        return
    if mongo_db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    token = message.command[1][7:]
    record = mongo_db.channel_batch_links.find_one({"token": token}) or mongo_db.channel_batch_links.find_one({"token": message.command[1]})
    if not record:
        await message.reply("❌ Invalid or expired batch link.")
        raise StopPropagation

    payload = message.command[1]
    access_res = await cmd.access_verification(client, message.from_user.id, payload)
    if isinstance(access_res, tuple):
        v_text, access_markup = access_res
    else:
        v_text, access_markup = "<b>🔐 Please verify first to access this batch.</b>", access_res
    if access_markup:
        await message.reply(v_text, reply_markup=access_markup, disable_web_page_preview=True)
        raise StopPropagation
    if await cmd.send_fsub_prompt(client, message, payload):
        raise StopPropagation

    user_id = int(message.from_user.id)
    delivery_key = (int(client.me.id), user_id)
    _ACTIVE_DELIVERIES[delivery_key] = True

    cancel_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("• cancel", callback_data=f"cbatch_cancel_{token}")]
    ])
    wait_msg = await message.reply("Please wait...\n\n• cancel", reply_markup=cancel_btn)

    f_id = int(record["first_msg_id"])
    l_id = int(record["last_msg_id"])
    ch_id = int(record["channel_id"])
    rec = cmd.bot_record(client)
    protected = bool(record.get("protected", False)) or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

    custom_btns = rec.get("custom_buttons", [])
    markup = None
    if custom_btns:
        rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
        if rows:
            markup = InlineKeyboardMarkup(rows)

    custom_cap = rec.get("custom_caption")
    invert_cap = bool(rec.get("invert_caption", False))
    spoiler_anim = bool(rec.get("spoiler_animation", False))

    for m_id in range(f_id, l_id + 1):
        if not _ACTIVE_DELIVERIES.get(delivery_key, False):
            break
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(ch_id, m_id)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        base_kw = {
            "chat_id": user_id,
            "from_chat_id": ch_id,
            "message_id": m_id,
            "caption": caption_to_use,
            "reply_markup": markup,
            "protect_content": protected,
        }
        if caption_to_use:
            base_kw["parse_mode"] = enums.ParseMode.HTML

        attempts = []
        kw1 = dict(base_kw)
        if invert_cap:
            kw1["invert_media"] = True
        if spoiler_anim:
            kw1["has_spoiler"] = True
        attempts.append(kw1)

        if invert_cap or spoiler_anim:
            kw2 = dict(base_kw)
            if invert_cap:
                kw2["show_caption_above_media"] = True
            if spoiler_anim:
                kw2["has_spoiler"] = True
            attempts.append(kw2)

        if spoiler_anim:
            attempts.append({**base_kw, "has_spoiler": True})

        attempts.append(base_kw)
        fb_no_pm = dict(base_kw)
        fb_no_pm.pop("parse_mode", None)
        attempts.append(fb_no_pm)

        for attempt_kw in attempts:
            try:
                await client.copy_message(**attempt_kw)
                await asyncio.sleep(0.1)
                break
            except Exception:
                continue

    _ACTIVE_DELIVERIES.pop(delivery_key, None)
    try:
        await wait_msg.delete()
    except Exception:
        pass

    raise StopPropagation


async def callback_cancel(client, query):
    data = query.data or ""
    if not data.startswith("cbatch_cancel_"):
        return
    delivery_key = (int(client.me.id), int(query.from_user.id))
    _ACTIVE_DELIVERIES[delivery_key] = False
    await query.answer("Delivery cancelled.")
    try:
        await query.message.delete()
    except Exception:
        pass
    raise StopPropagation


def register(client, base_group=-102):
    private = filters.private
    client.add_handler(MessageHandler(batch_start_deliver, filters.command("start") & private), group=base_group)
    client.add_handler(MessageHandler(start_batch, filters.command("batch") & private), group=base_group)
    client.add_handler(MessageHandler(capture_batch_step, private), group=base_group + 1)
    client.add_handler(CallbackQueryHandler(callback_cancel, filters.regex(r"^cbatch_cancel_")), group=base_group)
    return client
