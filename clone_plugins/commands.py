# ASH FILE STORE & CLONE MANAGER
# Telegram: @movies_1780

import asyncio
import random
import base64
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery, InputMediaPhoto
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info
from plugins.clone import mongo_db
from config import BOT_USERNAME, ADMINS, PICS, CUSTOM_FILE_CAPTION, AUTO_DELETE_TIME, AUTO_DELETE
from Script import script
from validators import domain


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return f"{size:.2f} {units[i]}"


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    me = await client.get_me()
    if not await clonedb.is_user_exist(me.id, message.from_user.id):
        await clonedb.add_user(me.id, message.from_user.id)

    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton("💝 YouTube", url="https://www.youtube.com/@tech_as_0")
        ], [
            InlineKeyboardButton("🤖 Create Clone", url=f"https://t.me/{BOT_USERNAME}?start=clone")
        ], [
            InlineKeyboardButton("💁 Help", callback_data="help"),
            InlineKeyboardButton("About 🔻", callback_data="about")
        ]]
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.CLONE_START_TXT.format(message.from_user.mention, me.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    data = message.command[1]
    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, file_id = decoded.split("_", 1)
    except Exception:
        return await message.reply("❌ Invalid or expired file link.")

    try:
        msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            protect_content=(prefix == "filep"),
        )
        media = getattr(msg, msg.media.value)
        size = get_size(media.file_size) if getattr(media, "file_size", None) else "Unknown"
        name = getattr(media, "file_name", None) or "File"
        caption = f"<code>{name}</code>\n<code>Size: {size}</code>"
        if CUSTOM_FILE_CAPTION:
            try:
                caption = CUSTOM_FILE_CAPTION.format(
                    file_name=name,
                    file_size=size,
                    file_caption=getattr(media, "caption", "") or "",
                )
            except Exception:
                pass
        await msg.edit_caption(caption)

        warning = await msg.reply(
            f"<b>⚠️ This file will be deleted in {AUTO_DELETE} minutes.</b>\n"
            "Forward it to Saved Messages if you need it later."
        )
        await asyncio.sleep(AUTO_DELETE_TIME)
        await msg.delete()
        try:
            await warning.edit_text("<b>Your file has been deleted.</b>")
        except Exception:
            pass
    except Exception as e:
        await message.reply(f"❌ Unable to deliver this file: <code>{e}</code>")


@Client.on_message(filters.command("api") & filters.private)
async def shortener_api_handler(client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if len(message.command) == 1:
        return await message.reply(
            f"<b>Shortener API:</b> <code>{user.get('shortener_api') or 'Not set'}</code>\n"
            f"<b>Base Site:</b> <code>{user.get('base_site') or 'Not set'}</code>\n\n"
            "Use <code>/api YOUR_API_KEY</code> to update it."
        )
    if len(message.command) == 2:
        await update_user_info(user_id, {"shortener_api": message.command[1].strip()})
        return await message.reply("✅ Shortener API updated.")
    await message.reply("Usage: <code>/api YOUR_API_KEY</code>")


@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if len(message.command) == 1:
        return await message.reply(
            f"<b>Current base site:</b> <code>{user.get('base_site') or 'Not set'}</code>\n\n"
            "Use <code>/base_site example.com</code>."
        )
    if len(message.command) == 2:
        base_site = message.command[1].strip().replace("https://", "").replace("http://", "").rstrip("/")
        if base_site.lower() == "none":
            await update_user_info(user_id, {"base_site": None})
            return await message.reply("✅ Base site removed.")
        if not domain(base_site):
            return await message.reply("❌ Invalid domain. Example: <code>example.com</code>")
        await update_user_info(user_id, {"base_site": base_site})
        return await message.reply("✅ Base site updated.")
    await message.reply("Usage: <code>/base_site example.com</code>")


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    me = await client.get_me()
    if query.data == "close_data":
        return await query.message.delete()
    if query.data == "start":
        buttons = [[
            InlineKeyboardButton("💝 YouTube", url="https://www.youtube.com/@tech_as_0")
        ], [
            InlineKeyboardButton("🤖 Create Clone", url=f"https://t.me/{BOT_USERNAME}?start=clone")
        ], [
            InlineKeyboardButton("💁 Help", callback_data="help"),
            InlineKeyboardButton("About 🔻", callback_data="about")
        ]]
        return await query.message.edit_text(
            script.CLONE_START_TXT.format(query.from_user.mention, me.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    if query.data == "help":
        buttons = [[InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("🔒 Close", callback_data="close_data")]]
        return await query.message.edit_text(script.CHELP_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    if query.data == "about":
        owner = mongo_db.bots.find_one({"bot_id": me.id})
        owner_id = int(owner["user_id"]) if owner else 0
        buttons = [[InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("🔒 Close", callback_data="close_data")]]
        return await query.message.edit_text(
            script.CABOUT_TXT.format(me.mention, owner_id),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
