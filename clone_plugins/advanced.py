import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user
from plugins.clone import mongo_db
from config import ADMINS


def bot_record(client):
    if mongo_db is None: return {}
    try: return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}
    except Exception: return {}


def owner_only(client, user_id):
    doc = bot_record(client)
    if doc and int(doc.get("user_id", 0)) == int(user_id): return True
    try: return int(user_id) in {int(x) for x in ADMINS}
    except Exception: return False


def save(client, data):
    if mongo_db is not None: mongo_db.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


async def settings(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    d = bot_record(client)
    await message.reply("⚙️ <b>Clone Settings</b>\n\nForce Join: <code>%s</code>\nCaption: <code>%s</code>\nButtons: <code>%s</code>\nProtect: <code>%s</code>" % (len(d.get("force_channels", [])), "ON" if d.get("custom_caption") else "OFF", len(d.get("custom_buttons", [])), "ON" if d.get("protect_content") else "OFF"))


async def force_sub(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2: return await message.reply("Usage: /force_sub @channel or /force_sub off")
    if message.command[1].lower() == "off": save(client, {"force_channels": []}); return await message.reply("✅ Force Subscribe disabled.")
    try:
        chat = await client.get_chat(message.command[1]); channels = list(bot_record(client).get("force_channels", []))
        if chat.id not in channels: channels.append(chat.id)
        save(client, {"force_channels": channels}); await message.reply("✅ Force Subscribe added. Make the bot admin in that channel.")
    except Exception: await message.reply("❌ Cannot access that channel. Make the bot admin first.")


async def caption(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    raw = message.text.split(None, 1)[1] if len(message.command) > 1 else "off"
    if raw.lower() == "off": save(client, {"custom_caption": None}); return await message.reply("✅ Custom caption disabled.")
    save(client, {"custom_caption": raw}); await message.reply("✅ Custom caption saved. Variables: {file_name}, {file_size}, {file_caption}")


async def button(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2 or message.command[1].lower() == "off": save(client, {"custom_buttons": []}); return await message.reply("✅ Custom buttons cleared.")
    raw = message.text.split(None, 1)[1]
    if " - " not in raw: return await message.reply("Usage: /button Text - https://example.com")
    text, url = [x.strip() for x in raw.split(" - ", 1)]
    if not url.startswith(("https://", "http://")): return await message.reply("❌ Button URL must start with http:// or https://")
    buttons = list(bot_record(client).get("custom_buttons", [])); buttons.append({"text": text[:64], "url": url}); save(client, {"custom_buttons": buttons})
    await message.reply("✅ Custom button added.")


async def protect(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    value = len(message.command) > 1 and message.command[1].lower() in ("on", "1", "yes", "true")
    save(client, {"protect_content": value}); await message.reply("🔐 Protect Content: <b>%s</b>" % ("ON" if value else "OFF"))


async def admin_panel(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")], [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]])
    await message.reply("👑 <b>Owner Panel</b>", reply_markup=kb)


async def stats(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply("📊 <b>Users:</b> <code>%s</code>" % await clonedb.total_users_count(client.me.id))


async def broadcast(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if not message.reply_to_message: return await message.reply("Reply to a message and use /broadcast")
    sent = failed = 0
    async for u in clonedb.get_all_users(client.me.id):
        try: await message.reply_to_message.copy(u["user_id"]); sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
    await message.reply(f"📢 Done\nSent: {sent}\nFailed: {failed}")


async def ban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit(): return await message.reply("Usage: /ban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": True}}, upsert=True); await message.reply("🚫 User banned.")


async def unban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit(): return await message.reply("Usage: /unban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": False}}, upsert=True); await message.reply("✅ User unbanned.")


async def advanced_links(client, message):
    if not message.reply_to_message: return await message.reply("Reply to a supported file first.")
    cmd = message.command[0].lower()
    if cmd == "custom_batch": return await message.reply("Use /batch N after replying to the first file.")
    if cmd == "special_link": return await message.reply("Special link ready. Enable /protect on for protected delivery, then use /link.")
    return await message.reply("Universal link ready. Reply to a file and use /link.")


async def admin_callback(client, query):
    if not owner_only(client, query.from_user.id): return await query.answer("Owner only.", show_alert=True)
    action = query.data.split("_", 1)[1]; d = bot_record(client)
    if action == "stats": text = "📊 <b>Users:</b> <code>%s</code>" % await clonedb.total_users_count(client.me.id)
    elif action == "shortener":
        u = await get_user(query.from_user.id); text = "🔗 API: <code>%s</code>\nSite: <code>%s</code>" % (u.get("shortener_api") or "Not set", u.get("base_site") or "Not set")
    elif action == "broadcast": text = "📢 Reply to a message and use /broadcast"
    else: text = "⚙️ Force Join: %s\nCaption: %s\nButtons: %s\nProtect: %s" % (len(d.get("force_channels", [])), "ON" if d.get("custom_caption") else "OFF", len(d.get("custom_buttons", [])), "ON" if d.get("protect_content") else "OFF")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]))


async def admin_back(client, query):
    if not owner_only(client, query.from_user.id): return await query.answer("Owner only.", show_alert=True)
    await query.message.edit_text("👑 <b>Owner Panel</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")], [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]]))


def register(client):
    private = filters.private
    for fn, cmd in [(settings,"settings"),(force_sub,"force_sub"),(caption,"caption"),(button,"button"),(protect,"protect"),(admin_panel,"admin"),(stats,"stats"),(broadcast,"broadcast"),(ban,"ban"),(unban,"unban")]:
        client.add_handler(MessageHandler(fn, filters.command(cmd) & private), group=1)
    client.add_handler(MessageHandler(advanced_links, filters.command(["custom_batch","special_link","universal_link"]) & private), group=1)
    client.add_handler(CallbackQueryHandler(admin_callback, filters.regex(r"^admin_(settings|stats|broadcast|shortener)$")), group=1)
    client.add_handler(CallbackQueryHandler(admin_back, filters.regex(r"^admin_back$")), group=1)
    return client
