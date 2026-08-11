# ASH FILE STORE & CLONE MANAGER
# Telegram: @movies_1780

import asyncio
import random
import base64
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info, get_short_link
from plugins.clone import mongo_db
from config import BOT_USERNAME, PICS, CUSTOM_FILE_CAPTION, AUTO_DELETE_TIME, AUTO_DELETE
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


def bot_record(client):
    return mongo_db.bots.find_one({"bot_id": client.me.id})


def is_clone_owner(client, user_id):
    record = bot_record(client)
    return bool(record and int(record.get("user_id", 0)) == int(user_id))


async def force_channels(client):
    record = bot_record(client)
    return (record or {}).get("force_channels", [])


async def force_markup(client, user_id, payload):
    channels = await force_channels(client)
    missing = []
    for channel in channels:
        try:
            member = await client.get_chat_member(channel, user_id)
            if member.status in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED, enums.ChatMemberStatus.RESTRICTED):
                missing.append(channel)
        except Exception:
            missing.append(channel)
    if not missing:
        return None
    rows = []
    for channel in missing:
        try:
            chat = await client.get_chat(channel)
            url = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
            if url:
                rows.append([InlineKeyboardButton(f"📢 Join {chat.title[:20]}", url=url)])
        except Exception:
            pass
    rows.append([InlineKeyboardButton("✅ I Joined", callback_data=f"verify:{payload}")])
    return InlineKeyboardMarkup(rows)


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    me = await client.get_me()
    if not await clonedb.is_user_exist(me.id, message.from_user.id):
        await clonedb.add_user(me.id, message.from_user.id)

    if len(message.command) != 2:
        buttons = [
            [InlineKeyboardButton("💝 YouTube", url="https://www.youtube.com/@tech_as_0")],
            [InlineKeyboardButton("🤖 Create Clone", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("💁 Help", callback_data="help"), InlineKeyboardButton("About 🔻", callback_data="about")],
        ]
        return await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.CLONE_START_TXT.format(message.from_user.mention, me.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    data = message.command[1]
    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, file_id = decoded.split("_", 1)
    except Exception:
        return await message.reply("❌ Invalid or expired file link.")

    markup = await force_markup(client, message.from_user.id, data)
    if markup:
        return await message.reply("<b>🔐 Join the required channel(s) first.</b>", reply_markup=markup)

    try:
        msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            protect_content=(prefix == "filep"),
        )
        media = getattr(msg, msg.media.value, None)
        size = get_size(media.file_size) if media and getattr(media, "file_size", None) else "Unknown"
        name = getattr(media, "file_name", None) if media else None
        name = name or "File"
        caption = f"<code>{name}</code>\n<code>Size: {size}</code>"
        if CUSTOM_FILE_CAPTION:
            try:
                caption = CUSTOM_FILE_CAPTION.format(file_name=name, file_size=size, file_caption=getattr(media, "caption", "") or "")
            except Exception:
                pass
        try:
            await msg.edit_caption(caption)
        except Exception:
            pass
        warning = await msg.reply(f"<b>⚠️ This file will be deleted in {AUTO_DELETE} minutes.</b>")
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
        return await message.reply(f"<b>Shortener API:</b> <code>{user.get('shortener_api') or 'Not set'}</code>\n<b>Base Site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    if len(message.command) == 2:
        await update_user_info(user_id, {"shortener_api": message.command[1].strip()})
        return await message.reply("✅ Shortener API updated.")
    await message.reply("Usage: <code>/api YOUR_API_KEY</code>")


@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, message: Message):
    user_id = message.from_user.id
    if len(message.command) == 1:
        user = await get_user(user_id)
        return await message.reply(f"<b>Current base site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    base_site = message.command[1].strip().replace("https://", "").replace("http://", "").rstrip("/")
    if base_site.lower() == "none":
        await update_user_info(user_id, {"base_site": None})
        return await message.reply("✅ Base site removed.")
    if not domain(base_site):
        return await message.reply("❌ Invalid domain. Example: <code>example.com</code>")
    await update_user_info(user_id, {"base_site": base_site})
    await message.reply("✅ Base site updated.")


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    me = await client.get_me()
    if query.data == "close_data":
        return await query.message.delete()
    if query.data.startswith("verify:"):
        payload = query.data.split(":", 1)[1]
        markup = await force_markup(client, query.from_user.id, payload)
        if markup:
            return await query.answer("❌ You still need to join the required channel(s).", show_alert=True)
        await query.answer("✅ Verified!")
        try:
            await query.message.delete()
        except Exception:
            pass
        return await client.send_message(query.from_user.id, "<b>✅ Verification successful. Open your file link again.</b>")
    if query.data == "start":
        buttons = [
            [InlineKeyboardButton("💝 YouTube", url="https://www.youtube.com/@tech_as_0")],
            [InlineKeyboardButton("🤖 Create Clone", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("💁 Help", callback_data="help"), InlineKeyboardButton("About 🔻", callback_data="about")],
        ]
        text = script.CLONE_START_TXT.format(query.from_user.mention, me.mention)
        if query.message.photo:
            return await query.message.edit_caption(text, reply_markup=InlineKeyboardMarkup(buttons))
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    if query.data == "help":
        buttons = [[InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("🔒 Close", callback_data="close_data")]]
        return await query.message.edit_text(script.CHELP_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    if query.data == "about":
        owner = mongo_db.bots.find_one({"bot_id": me.id})
        owner_id = int(owner["user_id"]) if owner else 0
        buttons = [[InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("🔒 Close", callback_data="close_data")]]
        return await query.message.edit_text(script.CABOUT_TXT.format(me.mention, owner_id), reply_markup=InlineKeyboardMarkup(buttons))
