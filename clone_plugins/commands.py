# ASH FILE STORE & CLONE MANAGER
import asyncio
import random
import base64
import secrets
import time
from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info, get_short_link, format_caption
from plugins.clone import mongo_db
from config import BOT_USERNAME, PICS, CUSTOM_FILE_CAPTION, ADMINS, UPDATE_CHANNEL, tg_link
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


def owner_id(client): return int(bot_record(client).get("user_id", 0))


def is_owner_or_mod(client, user_id):
    uid = int(user_id)
    try:
        if uid in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    rec = bot_record(client)
    if not rec:
        from config import PUBLIC_FILE_STORE
        return bool(PUBLIC_FILE_STORE)
    if int(rec.get("user_id", 0)) == uid:
        return True
    if uid in [int(x) for x in rec.get("moderators", [])]:
        return True
    if rec.get("mode") == "public":
        return True
    from config import PUBLIC_FILE_STORE
    return bool(PUBLIC_FILE_STORE)


def make_file_link(bot_username, file_id, protected=False):
    prefix = "filep" if protected else "file"
    raw = f"{prefix}_{file_id}".encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"https://t.me/{bot_username}?start={payload}"


async def force_markup(client, user_id, original_payload):
    channels = bot_record(client).get("force_channels", [])
    if not channels: return None
    missing = []
    for ch in channels:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"): missing.append(ch)
        except Exception:
            missing.append(ch)
    if not missing: return None
    buttons = []
    for ch in missing:
        try:
            chat = await client.get_chat(ch)
            link = chat.invite_link or f"https://t.me/{chat.username}"
            title = chat.title or str(ch)
            buttons.append([InlineKeyboardButton(f"📢 Join {title[:20]}", url=link)])
        except Exception:
            pass
    buttons.append([InlineKeyboardButton("🔄 Try Again", callback_data=f"verify:{original_payload}")])
    return InlineKeyboardMarkup(buttons)


async def access_verification(client, user_id, original_payload):
    return None


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("LINK SHORTENER 🔗", callback_data="link_shortener")],
        [InlineKeyboardButton("CUSTOM CAPTION 🖊️", callback_data="custom_caption")],
        [InlineKeyboardButton("CUSTOM BUTTON ➕", callback_data="custom_button")],
        [InlineKeyboardButton("PROTECT CONTENT ☂️", callback_data="protect_menu")],
        [InlineKeyboardButton("❮ BACK", callback_data="start_back")],
    ])


async def deliver_file(client, user_id, file_id, protected=False):
    rec = bot_record(client)
    protected = protected or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    msg = await client.send_cached_media(user_id, file_id, protect_content=protected)
    media = getattr(msg, msg.media.value, None) if msg.media else None
    size = get_size(media.file_size) if media and getattr(media, "file_size", None) else "Unknown"
    name = getattr(media, "file_name", None) if media else None or "File"
    caption_template = rec.get("custom_caption") or CUSTOM_FILE_CAPTION or f"<code>{name}</code>\n<code>Size: {size}</code>"
    caption = format_caption(caption_template, media=media, source_msg=msg, default_caption=f"<code>{name}</code>\n<code>Size: {size}</code>")
    try:
        await msg.edit_caption(caption, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await msg.edit_caption(caption)
        except Exception:
            pass
    buttons = rec.get("custom_buttons", [])
    rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons if b.get("text") and b.get("url")]
    if rows:
        try: await msg.edit_reply_markup(InlineKeyboardMarkup(rows))
        except Exception: pass
    if rec.get("auto_delete_enabled", False):
        minutes = max(1, int(rec.get("auto_delete_minutes", 15)))
        warning = await msg.reply(f"<b>⚠️ This file will be deleted in {minutes} minutes.</b>")
        await asyncio.sleep(minutes * 60)
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
        buttons = [
            [InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
            [InlineKeyboardButton("🤖 CREATE MY OWN CLONE", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("📢 UPDATE CHANNEL", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))]
        ]
        caption = script.CLONE_START_TXT.format(message.from_user.mention, me.mention)
        rec = bot_record(client)
        start_photo = rec.get("start_pic") or random.choice(PICS)
        try: return await message.reply_photo(photo=start_photo, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            try: return await message.reply_photo(photo=random.choice(PICS), caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception: return await message.reply(caption, reply_markup=InlineKeyboardMarkup(buttons))
    data = message.command[1]
    if data.lower() in ("clone", "settings"):
        from clone_plugins import clone_settings_ui as cset
        return await cset.settings(client, message)
    try:
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("ascii")
        prefix, file_id = decoded.split("_", 1)
    except Exception: return await message.reply("❌ Invalid or expired link.")
    if prefix == "verify":
        if mongo_db is None: return await message.reply("❌ Verification database is not configured.")
        rec = mongo_db.access_tokens.find_one({"bot_id": client.me.id, "token": file_id, "user_id": int(message.from_user.id)})
        if not rec or int(rec.get("expires_at", 0)) <= int(time.time()): return await message.reply("❌ Verification expired. Open the original file link again.")
        mongo_db.access_tokens.update_one({"_id": rec["_id"]}, {"$set": {"verified_at": int(time.time()), "expires_at": int(time.time()) + max(1, int(bot_record(client).get("access_token_hours", 1))) * 3600}})
        return await client.send_message(message.from_user.id, "✅ <b>Verification successful.</b>\n\nOpen your file link again.")
    if prefix not in ("file", "filep") or not file_id: return await message.reply("❌ Invalid or expired file link.")
    access_markup = await access_verification(client, message.from_user.id, data)
    if access_markup: return await message.reply("<b>🔐 Please verify first to access this file.</b>", reply_markup=access_markup)
    markup = await force_markup(client, message.from_user.id, data)
    if markup: return await message.reply("<b>🔐 Please join the required channel(s) first.</b>", reply_markup=markup)
    try: await deliver_file(client, message.from_user.id, file_id, protected=prefix == "filep")
    except Exception as e: await message.reply(f"❌ Unable to deliver file: <code>{e}</code>")


async def help_command(client, message):
    text=("📚 <b>ASH FILE STORE — HELP</b>\n\n👤 <b>User Commands</b>\n• /start — Check bot / open file link\n• /help — Open this help\n• /getlink — Create a single shareable file link\n• /custom_batch — Create custom batch links\n• /shortener — Shortener settings\n• /settings — Customize bot\n• /api KEY — Set shortener API\n• /base_site SITE — Set shortener site\n• /clone — Create your own clone\n\n👑 <b>Owner / Moderator</b>\n• /admin • /stats • /broadcast\n• /ban • /unban • /force_sub\n• /caption • /button • /protect\n• /auto_delete • /no_forward • /moderator\n• /access_token • /transfer_db • /deactivate\n• /mode • /restart • /delete • /start_msg\n\n⚙️ Owner features are also available from <b>Settings → My Clone Bot</b>.")
    await message.reply(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ SETTINGS",callback_data="settings")]]))


async def genlink(client, message):
    if not is_owner_or_mod(client,message.from_user.id) and bot_record(client).get("mode","private")=="private": return await message.reply("❌ Link generation is private. Only owner/moderators can use it.")
    replied=message.reply_to_message
    if not replied or not replied.media: return await message.reply("Reply to a video, audio or document and use <code>/link</code>.")
    media=getattr(replied,replied.media.value,None); file_id=getattr(media,"file_id",None)
    if not file_id: return await message.reply("❌ Supported media: video, audio or document.")
    rec=bot_record(client); protected=bool(rec.get("protect_content",False)) or bool(rec.get("no_forward",False)); username=(await client.get_me()).username; link=make_file_link(username,file_id,protected)
    await message.reply(f"🔗 <b>File Link:</b>\n{link}")


async def custom_batch(client,message): return await message.reply("Use /custom_batch or /batch.")
async def special_link(client,message): return await genlink(client,message)
async def universal_link(client,message): return await genlink(client,message)


async def api_handler(client,message):
    uid=owner_id(client) or message.from_user.id; user=await get_user(uid)
    if len(message.command)==1: return await message.reply(f"<b>Shortener API:</b> <code>{user.get('shortener_api') or 'Not set'}</code>\n<b>Base Site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    await update_user_info(uid,{"shortener_api":message.command[1].strip()}); await message.reply("✅ Shortener API updated successfully.")


async def base_site_handler(client,message):
    uid=owner_id(client) or message.from_user.id
    if len(message.command)==1:
        user=await get_user(uid); return await message.reply(f"<b>Current base site:</b> <code>{user.get('base_site') or 'Not set'}</code>")
    site=message.command[1].strip().replace("https://","").replace("http://","").rstrip("/")
    if site.lower()=="none": await update_user_info(uid,{"base_site":None}); return await message.reply("✅ Base site removed.")
    if not domain(site): return await message.reply("❌ Invalid domain.")
    await update_user_info(uid,{"base_site":site}); await message.reply("✅ Base site updated successfully.")


async def shortener(client, message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not (user.get("base_site") and user.get("shortener_api")):
        rec = bot_record(client)
        if rec.get("base_site") and rec.get("shortener_api"):
            user = {"base_site": rec.get("base_site"), "shortener_api": rec.get("shortener_api")}
        else:
            return await message.reply(
                "<b>Link Shortener</b>\n\n"
                "To shorten your links using your preferred provider, make sure to connect it with me first.\n\n"
                "Use /settings to connect your shortener provider."
            )
    ans = await client.ask(message.chat.id, "Send your Link which you want to shorten", timeout=120)
    link = (ans.text or "").strip()
    if not link or link.startswith("/"):
        return await message.reply("❌ Invalid link or cancelled.")
    short_link = await get_short_link(user, link)
    if not short_link or short_link == link:
        return await message.reply("Something went wrong, please try later")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 SHARE SHORTENED LINK ↗️", url=f"https://t.me/share/url?url={short_link}")]
    ])
    await message.reply(
        f"Here is your shortened link:\n\n{short_link}",
        reply_markup=markup,
        disable_web_page_preview=True
    )


async def settings_command(client, message):
    text = "🛠️ <b>Settings</b>\n\nCustomize your settings as your need"
    return await message.reply(text, reply_markup=settings_menu())


async def callbacks(client, query):
    data = query.data
    if data == "close_data":
        return await query.message.delete()
    if data.startswith("verify:"):
        payload = data.split(":", 1)[1]
        markup = await force_markup(client, query.from_user.id, payload)
        if markup:
            return await query.answer("❌ Join all required channels first.", show_alert=True)
        await query.answer("✅ Verified!")
        try:
            await query.message.delete()
        except Exception:
            pass
        return await client.send_message(query.from_user.id, "<b>✅ Verification successful. Open your file link again.</b>")
    if data == "help":
        return await help_command(client, query.message)
    if data == "about":
        me = client.me or (await client.get_me())
        owner_id_val = owner_id(client) or query.from_user.id
        owner_name = "Ash"
        try:
            owner_user = await client.get_users(owner_id_val)
            owner_name = owner_user.first_name or "Owner"
        except Exception:
            pass
        about_text = script.CABOUT_TXT.format(
            me.first_name,
            BOT_USERNAME,
            "MD File Store Bot",
            owner_id_val,
            owner_name
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="start_back")]])
        if query.message.photo:
            return await query.message.edit_caption(caption=about_text, reply_markup=markup)
        return await query.message.edit_text(about_text, reply_markup=markup)
    if data == "start_back":
        me = client.me or (await client.get_me())
        buttons = [
            [InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
            [InlineKeyboardButton("🤖 CREATE MY OWN CLONE", url=f"https://t.me/{BOT_USERNAME}?start=clone")],
            [InlineKeyboardButton("📢 UPDATE CHANNEL", url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"))]
        ]
        caption = script.CLONE_START_TXT.format(query.from_user.mention, me.mention)
        if query.message.photo:
            return await query.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        return await query.message.edit_text(caption, reply_markup=InlineKeyboardMarkup(buttons))
    # Settings callbacks are fully handled by clone_settings_ui
    if data in (
        "settings", "settings_back", "link_shortener", "add_shortener", "delete_shortener",
        "custom_caption", "caption_see", "caption_delete", "caption_edit",
        "custom_button", "button_add", "button_delete", "protect_menu", "protect_toggle", "protect_on", "protect_off"
    ):
        return
    return await query.answer("Unknown option.", show_alert=True)


def register(client):
    private=filters.private
    client.add_handler(MessageHandler(start,filters.command("start")&private),group=0)
    client.add_handler(MessageHandler(help_command,filters.command("help")&private),group=0)
    client.add_handler(MessageHandler(genlink,filters.command(["link","genlink"])&private),group=1)
    client.add_handler(MessageHandler(universal_link,filters.command("universal_link")&private),group=1)
    client.add_handler(MessageHandler(api_handler,filters.command("api")&private),group=1)
    client.add_handler(MessageHandler(base_site_handler,filters.command("base_site")&private),group=1)
    client.add_handler(MessageHandler(shortener,filters.command("shortener")&private),group=1)
    client.add_handler(MessageHandler(settings_command,filters.command("settings")&private),group=1)
    client.add_handler(CallbackQueryHandler(callbacks,filters.regex(r"^(close_data|verify:.*|help|about|start_back|settings|settings_back|my_clone|google_backup|google_connect|link_shortener|add_shortener|delete_shortener|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete|protect_menu|protect_on|protect_off)$")),group=0)
    return client
