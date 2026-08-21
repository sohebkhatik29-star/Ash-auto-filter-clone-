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
from clone_plugins import master_manager

MAX_USER_CLONES = master_manager.MAX_USER_CLONES

manage_clones_markup = master_manager.manage_clones_markup
master_settings.manage_clones_markup = manage_clones_markup

@Client.on_callback_query(filters.regex(r"^clone_limit$"))
async def clone_limit(client, query):
    await query.answer("❌ You can create maximum 5 clone bots.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^create_clone_prompt$"))
async def create_clone_prompt(client, query):
    return await master_manager.handle_clone_callbacks(client, query)

# IMPORTANT: do not register a second handler for clone_my_bots here.
# master_manager.handle_clone_callbacks already handles that callback.
# Keeping a second handler makes Telegram receive/render the same panel twice.

@Client.on_message(filters.command("start") & filters.private)
async def clone_only_start(client, message):
    """Clone-only /start menu. Other commands and buttons stay untouched."""
    if len(message.command) != 1:
        return
    m = master_manager.db()
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
    m = master_manager.db()
    if m is None or m.bots.find_one({"bot_id": client.me.id}):
        return
    from plugins.master_settings import send_manage_clones
    await send_manage_clones(client, message.from_user.id)
    raise StopPropagation
