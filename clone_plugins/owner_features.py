"""Owner settings/features for cloned file-store bots.
Keeps each clone's settings isolated by bot id.
"""
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from plugins.clone import mongo_db


def owner_id_for(bot_id):
    row = mongo_db.bots.find_one({"bot_id": bot_id})
    return int(row["user_id"]) if row and row.get("user_id") else None


def settings_for(bot_id):
    row = mongo_db.clone_settings.find_one({"bot_id": bot_id})
    if not row:
        row = {"bot_id": bot_id, "force_sub": None, "caption": None, "buttons": [], "verify": False}
        mongo_db.clone_settings.insert_one(row)
    return row


def owner_only(func):
    async def wrapper(client, message):
        me = await client.get_me()
        owner = owner_id_for(me.id)
        if owner != message.from_user.id:
            return await message.reply_text("❌ This command is only for the clone owner.")
        return await func(client, message)
    wrapper.__name__ = func.__name__
    return wrapper


@Client.on_message(filters.command("settings") & filters.private)
async def settings(client, message):
    me = await client.get_me()
    s = settings_for(me.id)
    fs = s.get("force_sub") or "Not set"
    caption = "Enabled" if s.get("caption") else "Default"
    buttons = len(s.get("buttons") or [])
    text = (
        "⚙️ <b>Clone Settings</b>\n\n"
        f"Force Subscribe: <code>{fs}</code>\n"
        f"Custom Caption: <b>{caption}</b>\n"
        f"Custom Buttons: <b>{buttons}</b>\n"
        f"Verification: <b>{'ON' if s.get('verify') else 'OFF'}</b>\n\n"
        "Owner commands:\n"
        "<code>/force_sub @channel</code>\n"
        "<code>/force_sub off</code>\n"
        "<code>/caption your text</code>\n"
        "<code>/caption off</code>\n"
        "<code>/button Text | https://example.com</code>\n"
        "<code>/button off</code>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="clone_settings_refresh")]]))


@Client.on_message(filters.command("force_sub") & filters.private)
@owner_only
async def force_sub(client, message):
    me = await client.get_me()
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/force_sub @channel</code> or <code>/force_sub off</code>")
    value = message.command[1].strip()
    mongo_db.clone_settings.update_one({"bot_id": me.id}, {"$set": {"force_sub": None if value.lower() == "off" else value}}, upsert=True)
    await message.reply_text("✅ Force Subscribe updated.\n\nNote: the bot must be an admin in the channel for membership checks.")


@Client.on_message(filters.command("caption") & filters.private)
@owner_only
async def caption(client, message):
    me = await client.get_me()
    value = message.text.partition(" ")[2].strip()
    if not value:
        return await message.reply_text("Usage: <code>/caption Your caption {file_name} {file_size}</code>\nOr: <code>/caption off</code>")
    mongo_db.clone_settings.update_one({"bot_id": me.id}, {"$set": {"caption": None if value.lower() == "off" else value}}, upsert=True)
    await message.reply_text("✅ Custom caption updated.")


@Client.on_message(filters.command("button") & filters.private)
@owner_only
async def button(client, message):
    me = await client.get_me()
    value = message.text.partition(" ")[2].strip()
    if value.lower() == "off":
        mongo_db.clone_settings.update_one({"bot_id": me.id}, {"$set": {"buttons": []}}, upsert=True)
        return await message.reply_text("✅ Custom buttons removed.")
    if "|" not in value:
        return await message.reply_text("Usage: <code>/button Button Text | https://example.com</code>")
    text, url = [x.strip() for x in value.split("|", 1)]
    if not re.match(r"^https?://", url):
        return await message.reply_text("❌ URL must start with http:// or https://")
    s = settings_for(me.id)
    buttons = s.get("buttons") or []
    buttons.append({"text": text, "url": url})
    mongo_db.clone_settings.update_one({"bot_id": me.id}, {"$set": {"buttons": buttons}}, upsert=True)
    await message.reply_text("✅ Button added.")


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    me = await client.get_me()
    owner = owner_id_for(me.id)
    text = (
        "<b>📚 FILE STORE HELP</b>\n\n"
        "/link - create a file link by replying to a file\n"
        "/genlink - create a generated file link\n"
        "/batch - create a batch link\n"
        "/settings - view clone settings\n"
        "/api - set shortener API\n"
        "/base_site - set shortener domain\n"
        "/shortener - shortener settings\n"
        "/custom_batch - custom batch\n"
        "/special_link - special link\n"
        "/universal_link - universal link\n"
    )
    if owner == message.from_user.id:
        text += "\n<b>👑 OWNER</b>\n/force_sub\n/caption\n/button\n/broadcast\n/stats"
    await message.reply_text(text)


@Client.on_message(filters.command("stats") & filters.private)
@owner_only
async def stats(client, message):
    me = await client.get_me()
    users = mongo_db.bots.find_one({"bot_id": me.id})
    count = mongo_db.clone_settings.count_documents({"bot_id": me.id})
    await message.reply_text(f"📊 <b>Clone Stats</b>\nSettings record: {count}\nBot ID: <code>{me.id}</code>")


@Client.on_callback_query(filters.regex("^clone_settings_refresh$"))
async def refresh_settings(client, query):
    await query.answer("Settings refreshed")
    await query.message.delete()
