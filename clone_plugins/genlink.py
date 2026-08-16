"""Single-file share-link flow for clone bots.

The only single-file link command is /getlink.
Usage: /getlink -> send/forward one message or file -> receive one link.
"""
import base64
import secrets
import time

from pyrogram import Client, filters, StopPropagation, enums
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_plugins.users_api import get_user, get_short_link, format_caption
from clone_plugins.commands import bot_record

_PENDING = {}


def _encode(token):
    return base64.urlsafe_b64encode(f"msg_{token}".encode()).decode().rstrip("=")


def _decode(payload):
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        prefix, token = raw.split("_", 1)
        return token if prefix == "msg" and token else None
    except Exception:
        return None


def _db():
    from plugins.clone import mongo_db
    return mongo_db


def _bot_owner(client, fallback):
    try:
        db = _db()
        if db is not None:
            row = db.bots.find_one({"bot_id": client.me.id}) or {}
            return int(row.get("user_id", 0)) or fallback
    except Exception:
        pass
    return fallback


async def interactive_getlink(client, message):
    _PENDING[(client.me.id, message.from_user.id)] = int(time.time())
    await message.reply(
        "📩 <b>Send or forward the message/file now.</b>\n\n"
        "I will create one shareable link automatically.\n\n"
        "/cancel - cancel"
    )
    raise StopPropagation


async def clean_help(client, message):
    text = (
        "📚 <b>ASH FILE STORE — HELP</b>\n\n"
        "👤 <b>User Commands</b>\n"
        "• /start — Check bot / open file link\n"
        "• /help — Open this help\n"
        "• /getlink — Create a single file/message link\n"
        "• /settings — Customize bot\n"
        "• /clone — Create your own clone\n\n"
        "👑 <b>Owner / Moderator</b>\n"
        "• /admin • /stats • /broadcast\n"
        "• /ban • /unban • /force_sub\n"
        "• /caption • /button • /protect\n"
        "• /auto_delete • /no_forward • /moderator\n"
        "• /access_token • /transfer_db • /deactivate\n"
        "• /mode • /restart • /delete • /start_msg\n\n"
        "⚙️ Owner features are also available from <b>Settings → My Clone Bot</b>."
    )
    await message.reply(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")]
        ]),
    )
    raise StopPropagation


async def capture_interactive(client, message):
    key = (client.me.id, message.from_user.id)
    if key not in _PENDING:
        return
    _PENDING.pop(key, None)

    if message.text and message.text.strip().lower() == "/cancel":
        await message.reply("❌ Cancelled.")
        raise StopPropagation
    if message.text and message.text.startswith("/"):
        await message.reply("❌ Send/forward the message or file, or use /cancel.")
        _PENDING[key] = int(time.time())
        raise StopPropagation

    db = _db()
    if db is None:
        await message.reply("❌ Database is not configured.")
        raise StopPropagation

    token = secrets.token_urlsafe(18)
    db.share_links.update_one(
        {"bot_id": client.me.id, "token": token},
        {"$set": {
            "bot_id": client.me.id,
            "token": token,
            "source_chat_id": int(message.chat.id),
            "source_message_id": int(message.id),
            "owner_id": int(message.from_user.id),
            "created_at": int(time.time()),
        }},
        upsert=True,
    )

    username = (await client.get_me()).username
    original = f"https://t.me/{username}?start={_encode(token)}"
    owner = _bot_owner(client, message.from_user.id)
    short = await get_short_link(await get_user(owner), original)
    link = short or original

    # Exactly one link is returned. There is no old /link reply flow and no
    # duplicate Original Link block.
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 SHARE URL", url=link)]
    ])

    await message.reply(
        "✅ <b>HERE IS YOUR LINK:</b>\n\n"
        f"🔗 <b>LINK:</b> {link}",
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    raise StopPropagation


async def open_interactive(client, message):
    if len(message.command) != 2:
        return
    payload = message.command[1]
    token = _decode(payload)
    if not token:
        return
    db = _db()
    if db is None:
        return
    record = db.share_links.find_one({"bot_id": client.me.id, "token": token})
    if not record:
        await message.reply("❌ This link is invalid or expired.")
        raise StopPropagation

    # Verification is generated directly inside Telegram so VERIFY & CONTINUE
    # does not depend on an external shortener URL.
    try:
        from clone_plugins.commands import bot_record, force_markup, is_owner_or_mod
        rec = bot_record(client)
        user_id = int(message.from_user.id)

        if rec.get("access_token_enabled", True) and not is_owner_or_mod(client, user_id):
            now = int(time.time())
            valid = db.access_tokens.find_one({
                "bot_id": client.me.id,
                "user_id": user_id,
                "payload": payload,
                "expires_at": {"$gt": now},
            })
            if not valid:
                access_token = secrets.token_urlsafe(18)
                hours = max(1, int(rec.get("access_token_hours", 1)))
                db.access_tokens.update_one(
                    {"bot_id": client.me.id, "user_id": user_id},
                    {"$set": {
                        "bot_id": client.me.id,
                        "user_id": user_id,
                        "token": access_token,
                        "payload": payload,
                        "expires_at": now + hours * 3600,
                    }},
                    upsert=True,
                )
                verify_payload = base64.urlsafe_b64encode(
                    f"verify_{access_token}".encode()
                ).decode().rstrip("=")
                username = (await client.get_me()).username
                verify_url = f"https://t.me/{username}?start={verify_payload}"
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 VERIFY & CONTINUE", url=verify_url)]
                ])
                await message.reply(
                    "<b>🔐 Please verify first to access this file.</b>",
                    reply_markup=markup,
                )
                raise StopPropagation

        force = await force_markup(client, user_id, payload)
        if force:
            await message.reply(
                "<b>🔐 Please join the required channel(s) first.</b>",
                reply_markup=force,
            )
            raise StopPropagation
    except StopPropagation:
        raise
    except Exception:
        pass

    try:
        rec = bot_record(client)
        is_protect = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))

        custom_btns = rec.get("custom_buttons", [])
        markup = None
        if custom_btns:
            rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in custom_btns if isinstance(b, dict) and b.get("text") and b.get("url")]
            if rows:
                markup = InlineKeyboardMarkup(rows)

        source_chat = int(record["source_chat_id"])
        source_mid = int(record["source_message_id"])

        custom_cap = rec.get("custom_caption")
        caption_to_use = None
        if custom_cap:
            try:
                src_msg = await client.get_messages(source_chat, source_mid)
                caption_to_use = format_caption(custom_cap, source_msg=src_msg)
            except Exception:
                caption_to_use = custom_cap

        try:
            delivered = await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=source_chat,
                message_id=source_mid,
                caption=caption_to_use,
                parse_mode=enums.ParseMode.HTML if caption_to_use else None,
                reply_markup=markup,
                protect_content=is_protect,
            )
        except Exception:
            delivered = await client.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=source_chat,
                message_id=source_mid,
                caption=caption_to_use,
                reply_markup=markup,
                protect_content=is_protect,
            )

        if rec.get("auto_delete_enabled", True):
            minutes = max(1, int(rec.get("auto_delete_minutes", 15)))
            warning = await client.send_message(
                chat_id=message.from_user.id,
                text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{minutes} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
            )
            import asyncio
            async def _auto_del():
                await asyncio.sleep(minutes * 60)
                try: await delivered.delete()
                except Exception: pass
                try: await warning.delete()
                except Exception: pass
            asyncio.create_task(_auto_del())
    except Exception:
        await message.reply(
            "❌ Unable to deliver this message. The original message may no longer be available."
        )
    raise StopPropagation


def register(client):
    private = filters.private

    # The ONLY single-file link command.
    client.add_handler(
        MessageHandler(interactive_getlink, filters.command("getlink") & private),
        group=-20,
    )

    # Keep help clean: no /link, /genlink, /batch or other link-generation
    # commands are advertised here.
    client.add_handler(
        MessageHandler(clean_help, filters.command("help") & private),
        group=-22,
    )

    client.add_handler(MessageHandler(capture_interactive, private), group=-19)
    client.add_handler(
        MessageHandler(open_interactive, filters.command("start") & private),
        group=-18,
    )
    return client


@Client.on_message(filters.command("getlink") & filters.private)
async def getlink_fallback(client, message):
    await interactive_getlink(client, message)
