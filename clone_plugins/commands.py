# ASH FILE STORE & CLONE MANAGER
import asyncio
import random
import base64
import secrets
import time
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info, get_short_link
from plugins.clone import mongo_db
from config import BOT_USERNAME, PICS, CUSTOM_FILE_CAPTION
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
    rec = bot_record(client)
    if int(rec.get("user_id", 0)) == int(user_id): return True
    return int(user_id) in [int(x) for x in rec.get("moderators", []) if str(x).isdigit()]


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
    rows.append([InlineKeyboardButton("✅ I Joined / Verify", callback_data=f"verify:{payload}")])
    return InlineKeyboardMarkup(rows)


async def access_verification(client, user_id, original_payload):
    rec = bot_record(client)
    if not rec.get("access_token_enabled", True) or is_owner_or_mod(client, user_id): return None
    if mongo_db is None: return None
    now = int(time.time())
    valid = mongo_db.access_tokens.find_one({"bot_id": client.me.id, "user_id": int(user_id), "expires_at": {"$gt": now}})
    if valid and valid.get("payload") == original_payload: return None
    token = secrets.token_urlsafe(18)
    hours = max(1, int(rec.get("access_token_hours", 1)))
    mongo_db.access_tokens.update_one({"bot_id": client.me.id, "user_id": int(user_id)}, {"$set": {"bot_id": client.me.id, "user_id": int(user_id), "token": token, "payload": original_payload, "expires_at": now + hours * 3600}}, upsert=True)
    verify_payload = base64.urlsafe_b64encode(f"verify_{token}".encode()).decode().rstrip("=")
    verify_url = f"https://t.me/{(await client.get_me()).username}?start={verify_payload}"
    owner = owner_id(client) or user_id
    short = await get_short_link(await get_user(owner), verify_url)
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔐 VERIFY & CONTINUE", url=short)]])


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT 🤖", callback_data="my_clone")],
        [InlineKeyboardButton("☁️ GOOGLE BACKUP", callback_data="google_backup")],
        [InlineKeyboardButton("🔗 LINK SHORTENER", callback_data="link_shortener")],
        [InlineKeyboardButton("✏️ CUSTOM CAPTION", callback_data="custom_caption")],
        [InlineKeyboardButton("🟢 CUSTOM BUTTON", callback_data="custom_button")],
        [InlineKeyboardButton("🛡️ PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings_back")],
    ])


async def deliver_file(client, user_id, file_id, protected=False):
    rec = bot_record(client)
    protected = protected or bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    msg = await client.send_cached_media(user_id, file_id, protect_content=protected)
    media = getattr(msg, msg.media.value, None) if msg.media else None
    size = get_size(media.file_size) if media and getattr(media, "file_size", None) else "Unknown"
    name = getattr(media, "file_name", None) if media else None or "File"
    caption = rec.get("custom_caption") or CUSTOM_FILE_CAPTION or f"<code>{name}</code>\n<code>Size: {size}</code>"
    try: caption = caption.format(file_name=name, file_size=size, file_caption=getattr(media, "caption", "") if media else "")
    except Exception: pass
    try: await msg.edit_caption(caption)
    except Exception: pass
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
        buttons = [[InlineKeyboardButton("💁 HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],[InlineKeyboardButton("🤖 CREATE MY OWN CLONE", url=f"https://t.me/{BOT_USERNAME}?start=clone")],[InlineKeyboardButton("📢 UPDATE CHANNEL", url="https://t.me/")]]
        caption = script.CLONE_START_TXT.format(message.from_user.mention, me.mention)
        try: return await message.reply_photo(photo=random.choice(PICS), caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception: return await message.reply(caption, reply_markup=InlineKeyboardMarkup(buttons))
    data = message.command[1]
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
    text=("📚 <b>ASH FILE STORE — HELP</b>\n\n👤 <b>User Commands</b>\n• /start — Check bot / open file link\n• /help — Open this help\n• /link — Create a shareable file link\n• /genlink — Create a file link\n• /batch N — Create batch links\n• /custom_batch N — Custom batch links\n• /special_link — Special link\n• /universal_link — Universal link\n• /shortener — Shortener settings\n• /settings — Customize bot\n• /api KEY — Set shortener API\n• /base_site SITE — Set shortener site\n• /clone — Create your own clone\n\n👑 <b>Owner / Moderator</b>\n• /admin • /stats • /broadcast\n• /ban • /unban • /force_sub\n• /caption • /button • /protect\n• /auto_delete • /no_forward • /moderator\n• /access_token • /transfer_db • /deactivate\n• /mode • /restart • /delete • /start_msg\n\n⚙️ Owner features are also available from <b>Settings → My Clone Bot</b>.")
    await message.reply(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ SETTINGS",callback_data="settings")]]))


async def genlink(client, message):
    if not is_owner_or_mod(client,message.from_user.id) and bot_record(client).get("mode","private")=="private": return await message.reply("❌ Link generation is private. Only owner/moderators can use it.")
    replied=message.reply_to_message
    if not replied or not replied.media: return await message.reply("Reply to a video, audio or document and use <code>/link</code>.")
    media=getattr(replied,replied.media.value,None); file_id=getattr(media,"file_id",None)
    if not file_id: return await message.reply("❌ Supported media: video, audio or document.")
    rec=bot_record(client); protected=bool(rec.get("protect_content",False)) or bool(rec.get("no_forward",False)); username=(await client.get_me()).username; link=make_file_link(username,file_id,protected); user=await get_user(owner_id(client) or message.from_user.id); short=await get_short_link(user,link)
    await message.reply(f"🔗 <b>File Link:</b>\n{short if short!=link else link}"+(f"\n\n🔗 <b>Original:</b>\n{link}" if short!=link else ""))


async def batch(client, message):
    if not is_owner_or_mod(client,message.from_user.id) and bot_record(client).get("mode","private")=="private": return await message.reply("❌ Batch generation is private. Only owner/moderators can use it.")
    replied=message.reply_to_message
    if not replied: return await message.reply("Reply to the first file and use <code>/batch N</code>.")
    try:
        count=int(message.command[1]) if len(message.command)>1 else 1
        if not 1<=count<=50: raise ValueError
    except ValueError: return await message.reply("Usage: <code>/batch 5</code> (1-50)")
    username=(await client.get_me()).username; rec=bot_record(client); protected=bool(rec.get("protect_content",False)) or bool(rec.get("no_forward",False)); links=[]
    for msg_id in range(replied.id,replied.id+count):
        try:
            msg=await client.get_messages(replied.chat.id,msg_id); media=getattr(msg,msg.media.value,None) if msg and msg.media else None; fid=getattr(media,"file_id",None)
            if fid: links.append(make_file_link(username,fid,protected))
        except Exception: pass
    if not links: return await message.reply("❌ No supported files found.")
    await message.reply("📦 <b>Batch Links</b>\n\n"+"\n".join(f"{i}. {x}" for i,x in enumerate(links,1)))


async def custom_batch(client,message): return await batch(client,message)
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


async def shortener(client,message):
    uid=owner_id(client) or message.from_user.id; user=await get_user(uid); await message.reply(f"🔗 <b>Link Shortener</b>\nAPI: <code>{user.get('shortener_api') or 'Not set'}</code>\nSite: <code>{user.get('base_site') or 'Not set'}</code>\n\nUse /api KEY and /base_site example.com to configure it.")


async def settings_command(client,message):
    if not is_owner_or_mod(client,message.from_user.id): return await message.reply("❌ Owner/moderator only.")
    await message.reply("⚙️ <b>Settings</b>\nCustomize your settings as your need.",reply_markup=settings_menu())


def settings_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🤖 MY CLONE BOT 🤖",callback_data="my_clone")],[InlineKeyboardButton("☁️ GOOGLE BACKUP",callback_data="google_backup")],[InlineKeyboardButton("🔗 LINK SHORTENER",callback_data="link_shortener")],[InlineKeyboardButton("✏️ CUSTOM CAPTION",callback_data="custom_caption")],[InlineKeyboardButton("🟢 CUSTOM BUTTON",callback_data="custom_button")],[InlineKeyboardButton("🛡️ PROTECT CONTENT",callback_data="protect_menu")],[InlineKeyboardButton("‹ BACK",callback_data="settings_back")]])


async def callbacks(client,query):
    data=query.data
    if data=="close_data": return await query.message.delete()
    if data.startswith("verify:"):
        payload=data.split(":",1)[1]; markup=await force_markup(client,query.from_user.id,payload)
        if markup: return await query.answer("❌ Join all required channels first.",show_alert=True)
        await query.answer("✅ Verified!")
        try: await query.message.delete()
        except Exception: pass
        return await client.send_message(query.from_user.id,"<b>✅ Verification successful. Open your file link again.</b>")
    if data=="help": return await help_command(client,query.message)
    if data=="about": return await query.answer("ASH FILE STORE & CLONE MANAGER",show_alert=True)
    if data in ("settings","settings_back"): return await query.message.edit_text("⚙️ <b>Settings</b>\nCustomize your settings as your need.",reply_markup=settings_menu())
    if data=="my_clone": return await query.message.edit_text(f"🛠 <b>Customize Clone</b>\n\n➜ <b>Name:</b> {client.me.first_name}\n\nConfigure Your Clone Settings Using Given Buttons",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("START MSG",callback_data="clone_startmsg"),InlineKeyboardButton("FORCE SUB",callback_data="clone_force")],[InlineKeyboardButton("MODERATORS",callback_data="clone_mods"),InlineKeyboardButton("AUTO DELETE",callback_data="clone_autodelete")],[InlineKeyboardButton("NO FORWARD",callback_data="clone_noforward"),InlineKeyboardButton("ACCESS TOKEN",callback_data="clone_access")],[InlineKeyboardButton("TRANSFER DB",callback_data="clone_transfer"),InlineKeyboardButton("DEACTIVATE",callback_data="clone_deactivate")],[InlineKeyboardButton("MODE",callback_data="clone_mode"),InlineKeyboardButton("RESTART",callback_data="clone_restart")],[InlineKeyboardButton("STATS",callback_data="clone_stats"),InlineKeyboardButton("DELETE",callback_data="clone_delete")],[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data=="google_backup": return await query.message.edit_text("☁️ <b>Google Backup</b>\n\nGoogle Drive backup is not configured in this deployment. Your clone data is stored in MongoDB.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data=="link_shortener":
        uid=owner_id(client) or query.from_user.id; u=await get_user(uid); return await query.message.edit_text(f"🔗 <b>Link Shortener</b>\n\nAPI: <code>{u.get('shortener_api') or 'Not set'}</code>\nSite: <code>{u.get('base_site') or 'Not set'}</code>\n\nSet with /api KEY and /base_site example.com",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data=="custom_caption":
        rec=bot_record(client); return await query.message.edit_text("✏️ <b>Custom Caption</b>\n\nUse /caption Your caption.\n\n<code>{file_name}</code> = File Name\n<code>{file_size}</code> = File Size\n<code>{file_caption}</code> = Original Caption\n\nCurrent: <code>%s</code>"%(rec.get("custom_caption") or "Default"),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data=="custom_button":
        rec=bot_record(client); return await query.message.edit_text("🟢 <b>Custom Button</b>\n\nUse /button Button Text - https://example.com\nUse /button off to clear all buttons.\n\nCurrent buttons: <code>%s</code>"%len(rec.get("custom_buttons",[])),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data=="protect_menu":
        rec=bot_record(client); status="Enabled ✅" if rec.get("protect_content") else "Disabled ❌"; return await query.message.edit_text(f"🛡️ <b>Protect Content</b>\n\nStatus: {status}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ON",callback_data="protect_on"),InlineKeyboardButton("OFF",callback_data="protect_off")],[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    if data in ("protect_on","protect_off"):
        if not is_owner_or_mod(client,query.from_user.id): return await query.answer("Owner only.",show_alert=True)
        if mongo_db is not None: mongo_db.bots.update_one({"bot_id":client.me.id},{"$set":{"protect_content":data=="protect_on"}},upsert=True)
        return await query.message.edit_text(f"🛡️ Protect Content: <b>{'Enabled ✅' if data=='protect_on' else 'Disabled ❌'}</b>",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data="settings")]]))
    return await query.answer("Unknown option.",show_alert=True)


def register(client):
    private=filters.private
    client.add_handler(MessageHandler(start,filters.command("start")&private),group=0)
    client.add_handler(MessageHandler(help_command,filters.command("help")&private),group=0)
    client.add_handler(MessageHandler(genlink,filters.command(["link","genlink"])&private),group=1)
    client.add_handler(MessageHandler(batch,filters.command("batch")&private),group=1)
    client.add_handler(MessageHandler(custom_batch,filters.command("custom_batch")&private),group=1)
    client.add_handler(MessageHandler(special_link,filters.command("special_link")&private),group=1)
    client.add_handler(MessageHandler(universal_link,filters.command("universal_link")&private),group=1)
    client.add_handler(MessageHandler(api_handler,filters.command("api")&private),group=1)
    client.add_handler(MessageHandler(base_site_handler,filters.command("base_site")&private),group=1)
    client.add_handler(MessageHandler(shortener,filters.command("shortener")&private),group=1)
    client.add_handler(MessageHandler(settings_command,filters.command("settings")&private),group=1)
    client.add_handler(CallbackQueryHandler(callbacks,filters.regex(r"^(close_data|verify:.*|help|about|settings|settings_back|my_clone|google_backup|link_shortener|custom_caption|custom_button|protect_menu|protect_on|protect_off)$")),group=0)
    return client
