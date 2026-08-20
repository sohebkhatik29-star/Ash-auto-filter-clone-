"""Focused clone-manager UI fixes.
Only changes the clone-management entry/menu and enforces a per-user 5-bot cap.
"""
import asyncio
import logging
import random
import re

from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMINS, BOT_USERNAME, PICS, UPDATE_CHANNEL, tg_link
from Script import script
from plugins import master_settings

MAX_USER_CLONES = 5


def _db():
    from plugins.clone import mongo_db
    return mongo_db


def _is_admin(uid):
    try:
        return int(uid) in {int(x) for x in ADMINS}
    except Exception:
        return False


def _docs(uid):
    m = _db()
    if m is None:
        return []
    q = {} if _is_admin(uid) else {"user_id": int(uid)}
    return list(m.bots.find(q, {"token": 0}).sort("bot_id", 1))


def manage_clones_markup(uid):
    docs = _docs(uid)
    rows = []
    for d in docs[:MAX_USER_CLONES]:
        bid = int(d["bot_id"])
        name = d.get("name") or d.get("username") or str(bid)
        rows.append([
            InlineKeyboardButton(
                f"🤖 @{name[:32]} ↗",
                callback_data=f"manage_clone:{bid}",
            )
        ])

    if len(docs) < MAX_USER_CLONES:
        rows.append([
            InlineKeyboardButton("➕ ADD BOT ➕", callback_data="create_clone_prompt")
        ])
    else:
        rows.append([
            InlineKeyboardButton("🚫 BOT LIMIT 5/5", callback_data="clone_limit")
        ])

    rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings_back")])
    return InlineKeyboardMarkup(rows)


# Replace only the clone-list menu used by the existing manager UI.
master_settings.manage_clones_markup = manage_clones_markup


@Client.on_callback_query(filters.regex(r"^clone_limit$"))
async def clone_limit(client, query):
    await query.answer("You can create maximum 5 clone bots.", show_alert=True)


async def _create_clone(client, user_id):
    from config import API_ID, API_HASH
    from plugins.clone import register_clone_handlers, set_clone_menu

    if len(_docs(user_id)) >= MAX_USER_CLONES:
        await client.send_message(user_id, "❌ <b>You can create maximum 5 clone bots.</b>")
        return

    token_msg = await client.ask(
        user_id,
        "1) Create a bot using @BotFather.\n"
        "2) Send the bot token here.\n\n"
        "Send /cancel to cancel."
    )
    if (token_msg.text or "").strip().lower() == "/cancel":
        await client.send_message(user_id, "<b>Cancelled 🚫</b>")
        return

    match = re.search(r"\b(\d+:[A-Za-z0-9_-]+)\b", token_msg.text or "")
    if not match:
        await client.send_message(
            user_id,
            "❌ <b>Could not read the bot token. Please send a valid token.</b>",
        )
        return

    bot_token = match.group(1)
    msg = await client.send_message(user_id, "👨‍💻 <b>Creating your clone...</b>")

    try:
        if len(_docs(user_id)) >= MAX_USER_CLONES:
            await msg.edit_text("❌ <b>You can create maximum 5 clone bots.</b>")
            return

        vj = Client(
            f"clone_{user_id}_{int(bot_token.split(':')[0])}",
            API_ID,
            API_HASH,
            bot_token=bot_token,
            plugins={},
        )
        await vj.start()
        register_clone_handlers(vj)
        bot = await vj.get_me()

        m = _db()
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
                "hide_owner": False,
            }},
            upsert=True,
        )
        await set_clone_menu(vj, int(user_id))
        await msg.edit_text("✨ <b>Successfully Cloned Your Bot</b>")
    except BaseException as e:
        logging.exception("Clone creation failed from manager")
        try:
            await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>")
        except Exception:
            pass


@Client.on_callback_query(filters.regex(r"^create_clone_prompt$"))
async def create_clone_prompt(client, query):
    user_id = int(query.from_user.id)
    if len(_docs(user_id)) >= MAX_USER_CLONES:
        return await query.answer(
            "You can create maximum 5 clone bots.",
            show_alert=True,
        )
    await query.answer()
    asyncio.create_task(_create_clone(client, user_id))


@Client.on_callback_query(filters.regex(r"^clone_my_bots$"))
async def clone_my_bots(client, query):
    """Open the owner's clone list directly from a cloned bot."""
    user_id = int(query.from_user.id)
    m = _db()
    if m is None:
        return await query.answer("Database is unavailable.", show_alert=True)

    # This callback is intended only for cloned bots.
    rec = m.bots.find_one({"bot_id": int(client.me.id)})
    if not rec:
        return await query.answer("This option is available from a cloned bot.", show_alert=True)

    await query.answer()
    from plugins.master_settings import send_manage_clones
    await send_manage_clones(client, user_id)


@Client.on_message(filters.command("start") & filters.private)
async def clone_only_start(client, message):
    """Clone-only /start menu. Other commands and buttons stay untouched."""
    if len(message.command) != 1:
        return

    m = _db()
    if m is None:
        return
    rec = m.bots.find_one({"bot_id": client.me.id})
    if not rec:
        return

    me = await client.get_me()
    buttons = [
        [
            InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"),
            InlineKeyboardButton(
                "🤖 MY OWN BOT",
                callback_data="clone_my_bots",
            ),
        ],
        [
            InlineKeyboardButton("💁 HELP", callback_data="help"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="about"),
        ],
        [
            InlineKeyboardButton(
                "📢 UPDATE CHANNEL",
                url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"),
            )
        ],
    ]
    caption = script.CLONE_START_TXT.format(
        message.from_user.mention,
        me.mention,
    )
    start_photo = rec.get("start_pic") or random.choice(PICS)
    try:
        await message.reply_photo(
            photo=start_photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception:
        await message.reply(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    raise StopPropagation


@Client.on_message(filters.command("start") & filters.private)
async def master_my_clones_start(client, message):
    """Deep-link target retained for backwards compatibility."""
    if len(message.command) != 2 or message.command[1].lower() != "my_clones":
        return

    m = _db()
    if m is None or m.bots.find_one({"bot_id": client.me.id}):
        return

    from plugins.master_settings import send_manage_clones
    await send_manage_clones(client, message.from_user.id)
    raise StopPropagation
