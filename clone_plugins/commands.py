# ASH FILE STORE & CLONE MANAGER

import asyncio
import random
import base64
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info, get_short_link
from plugins.clone import mongo_db
from config import BOT_USERNAME, PICS, CUSTOM_FILE_CAPTION, AUTO_DELETE_TIME, AUTO_DELETE
from Script import script
from validators import domain


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size); i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1; size /= 1024.0
    return f"{size:.2f} {units[i]}"


def bot_record(client):
    if mongo_db is None: return {}
    try: return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}
    except Exception: return {}


def force_channels(client): return bot_record(client).get("force_channels", [])


def make_file_link(username, file_id, protected=False):
    prefix = "filep" if protected else "file"
    payload = base64.urlsafe_b64encode(f"{prefix}_{file_id}".encode()).decode().rstrip("=")
    return f"https://t.me/{username}?start={payload}"


async def force_markup(client, user_id, payload):
    missing = []
    for channel in force_channels(client):
        try:
            member = await client.get_chat_member(channel, user_id)
            status = str(member.status).lower()
            if status.endswith(("left", "banned", "restricted", "kicked")): missing.append(channel)
        except Exception: missing.append(channel)
    if not missing: return None
    rows = []
    for channel in missing:
        try:
            chat = await client.get_chat(channel)
            url = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
            if url: rows.append([InlineKeyboardButton(f"📢 Join {chat.title[:24]}", url=url)])
        except Exception: pass
    rows.append([InlineKeyboardButton("✅ I Joined", callback_data=f"verify:{payload}")])
    return InlineKeyboardMarkup(rows)


async def deliver_file(client, user_id, file_id, protected=False):
    msg = await client.send_cached_media(user_id, file_id, protect_content=protected)
    media = getattr(msg, msg.media.value, None) if msg.media else None
    size = get_size(media.file_size) if media and getattr(media, "file_size", None) else "Unknown"
    name = getattr(media, "file_name", None) if media else None
    name = name or "File"
    settings = bot_record(client)
    caption = settings.get("custom_caption") or CUSTOM_FILE_CAPTION or f"<code>{name}</code>\n<code>Size: {size}</code>"
    try: caption = caption.format(file_name=name, file_size=size, file_caption=getattr(media, "caption", "") if media else "")
    except Exception: pass
    try: await msg.edit_caption(caption)
    except Exception: pass
    buttons = settings.get("custom_buttons", [])
    if buttons:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons if b.get("text") and b.get("url")])
        try: await msg.edit_reply_markup(markup)
        except Exception: pass
    if AUTO_DELETE:
        warning = await msg.reply(f"<b>⚠️ This file will be deleted in {AUTO_DELETE} minutes.</b>")
        await asyncio.sleep(AUTO_DELETE_TIME)
        try: await msg.delete()
        except Exception: pass
        try: await warning.edit_text("<b>Your file has been deleted.</b>")
        except Exception: pass
    return msg


async def start(client, message):
    me = await client.get_me()
    try:
        if not await clonedb.is_user_exist(me.id, message.from_user.id): await clonedb.add_user(me.id, message.from_user.id)
    except Exception: pass
    if len(message.command) != 2:
        buttons = [[InlineKeyboardButton("💝 YouTube", url="https://www.youtube.com/@tech_as_0")], [InlineKeyboardButton("🤖 Create Clone", url=f"https://t.me/{BOT_USERNAME}?start=clone")], [InlineKeyboardButton("💁 Help", callback_data="help"), InlineKeyboardButton("About 🔻", callback_data="about")]]
        try: return await message.reply_photo(photo=random.choice(PICS), caption=script.CLONE_START_TXT.format(message.from_user.mention, me.mention), reply_markup=InlineKeyboardMarkup(buttons))
        except Exception: return await message.reply(script.CLONE_START_TXT.format(message.from_user.mention, me.mention), reply_markup=InlineKeyboardMarkup(buttons))
    data = message.command[1]
    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, file_id = decoded.split("_", 1)
        if prefix not in ("file", "filep") or not file_id: raise ValueError
    except Exception: return await message.reply("❌ Invalid or expired file link.")
    markup = await force_markup(client, message.from_user.id, data)
    if markup: return await message.reply("<b>🔐 Join the required channel(s) first.</b>", reply_markup=markup)
    try: await deliver_file(client, message.from_user.id, file_id, protected=(prefix == "filep" or bot_record(client).get("protect_content", False)))
    except Exception as e: await message.reply(f"❌ Unable to deliver file: <code>{e}</code>")


async def help_command(client, message):
    text = ("📚 <b>ASH FILE STORE HELP</b>\n\n"
            "/start - Start / open a file link\n/help - Show commands\n"
            "/link - Create a shareable file link\n/genlink - Generate a file link\n/batch N - Batch links\n"
            "/custom_batch - Custom batch\n/special_link - Special link\n/universal_link - Universal link\n"
            "/shortener - Shortener settings\n/settings - Bot settings\n/api KEY - Set API\n/base_site example.com - Set site\n"
            "/clone - Create a clone\n\nOwner: /admin /stats /broadcast /ban /unban /force_sub /caption /button /protect")
    await message.reply(text)


async def genlink(client, message):
    replied = message.reply_to_message
    if not replied or not replied.media: return await message.reply("Reply to a video, audio or document and use <code>/link</code>.")
    media = getattr(replied, replied.media.value, None); file_id = getattr(media, "file_id", None)
    if not file_id: return await message.reply("❌ Supported media: video, audio or document.")
    protected = bool(bot_record(client).get("protect_content", False)); username = (await client.get_me()).username
    link = make_file_link(username, file_id, protected); user = await get_user(message.from_user.id); short = await get_short_link(user, link)
    await message.reply(f"🔗 <b>File Link:</b>\n{short if short != link else link}" + (f"\n\n🔗 <b>Original:</b>\n{link}" if short != link else ""))


async def batch(client, message):
    replied = message.reply_to_message
    if not replied: return await message.reply("Reply to the first file and use <code>/batch N</code>.")
    try:
        count = int(message.command[1]) if len(message.command) > 1 else 1
        if not 1 <= count <= 20: raise ValueError
    except ValueError: return await message.reply("Usage: <code>/batch 5</code> (1-20)")
    username = (await client.get_me()).username; protected = bool(bot_record(client).get("protect_content", False)); links = []
    for msg_id in range(replied.id, replied.id + count):
        try:
            msg = await client.get_messages(replied.chat.id, msg_id)
            media = getattr(msg, msg.media.value, None) if msg and msg.media else None; fid = getattr(media, "file_id", None)
            if fid: links.append(make_file_link(username, fid, protected))
        except Exception: pass
    if not links: return await message.reply("❌ No supported files found.")
    await message.reply("📦 <b>Batch Links</b>\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(links, 1)))


async def api_handler(client, message):
    user = await get_user(message.from_user.id)
    if len(message.command) == 1: return await message.reply(f"<b>Shortener API:</b> <code>{user.get('shortener_api') or 'Not set'}</code>\n<b>Base Site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    await update_user_info(message.from_user.id, {"shortener_api": message.command[1].strip()}); await message.reply("✅ Shortener API updated successfully.")


async def base_site_handler(client, message):
    if len(message.command) == 1:
        user = await get_user(message.from_user.id); return await message.reply(f"<b>Current base site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    site = message.command[1].strip().replace("https://", "").replace("http://", "").rstrip("/")
    if site.lower() == "none": await update_user_info(message.from_user.id, {"base_site": None}); return await message.reply("✅ Base site removed.")
    if not domain(site): return await message.reply("❌ Invalid domain.")
    await update_user_info(message.from_user.id, {"base_site": site}); await message.reply("✅ Base site updated successfully.")


async def shortener(client, message):
    user = await get_user(message.from_user.id)
    await message.reply(f"🔗 <b>Shortener</b>\nAPI: <code>{user.get('shortener_api') or 'Not set'}</code>\nSite: <code>{user.get('base_site') or 'Not set'}</code>")


async def callbacks(client, query):
    if query.data == "close_data": return await query.message.delete()
    if query.data.startswith("verify:"):
        payload = query.data.split(":", 1)[1]; markup = await force_markup(client, query.from_user.id, payload)
        if markup: return await query.answer("❌ Join all required channels first.", show_alert=True)
        await query.answer("✅ Verified!")
        try: await query.message.delete()
        except Exception: pass
        return await client.send_message(query.from_user.id, "<b>✅ Verification successful. Open your file link again.</b>")
    if query.data == "help":
        return await query.message.edit_text(getattr(script, "CHELP_TXT", "<b>ASH FILE STORE HELP</b>"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("🔒 Close", callback_data="close_data")]]))
    if query.data == "about": return await query.answer("ASH FILE STORE & CLONE MANAGER")
    if query.data == "start":
        me = await client.get_me(); text = script.CLONE_START_TXT.format(query.from_user.mention, me.mention)
        try: return await query.message.edit_caption(text)
        except Exception: return await query.message.edit_text(text)


def register(client):
    """Explicitly attach every handler to this exact Client instance."""
    private = filters.private
    client.add_handler(MessageHandler(start, filters.command("start") & private), group=0)
    client.add_handler(MessageHandler(help_command, filters.command("help") & private), group=0)
    client.add_handler(MessageHandler(genlink, filters.command(["link", "genlink"]) & private), group=1)
    client.add_handler(MessageHandler(batch, filters.command("batch") & private), group=1)
    client.add_handler(MessageHandler(api_handler, filters.command("api") & private), group=1)
    client.add_handler(MessageHandler(base_site_handler, filters.command("base_site") & private), group=1)
    client.add_handler(MessageHandler(shortener, filters.command("shortener") & private), group=1)
    client.add_handler(CallbackQueryHandler(callbacks, filters.regex(r"^(help|about|start|close_data|verify:.*)$")), group=0)
    return client
