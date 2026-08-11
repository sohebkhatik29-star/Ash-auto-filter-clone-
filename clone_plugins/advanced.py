# ASH FILE STORE & CLONE MANAGER - advanced clone features
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user
from plugins.clone import mongo_db


def bot_record(client):
    if mongo_db is None:
        return {}
    return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}


def owner_only(client, user_id):
    doc = bot_record(client)
    return bool(doc and int(doc.get("user_id", 0)) == int(user_id))


def save(client, data):
    mongo_db.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


@Client.on_message(filters.command("settings") & filters.private)
async def settings(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    d = bot_record(client)
    await message.reply("⚙️ <b>Clone Settings</b>\n\nForce Join: <code>%s</code>\nCaption: <code>%s</code>\nButtons: <code>%s</code>\nProtect: <code>%s</code>" % (len(d.get("force_channels", [])), "ON" if d.get("custom_caption") else "OFF", len(d.get("custom_buttons", [])), "ON" if d.get("protect_content") else "OFF"))


@Client.on_message(filters.command("force_sub") & filters.private)
async def force_sub(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2: return await message.reply("Usage: <code>/force_sub @channel</code> or <code>/force_sub off</code>")
    if message.command[1].lower() == "off":
        save(client, {"force_channels": []}); return await message.reply("✅ Force Subscribe disabled.")
    channel = message.command[1]
    try:
        chat = await client.get_chat(channel)
        await client.get_chat_member(chat.id, client.me.id)
        channels = list(bot_record(client).get("force_channels", []))
        if chat.id not in channels: channels.append(chat.id)
        save(client, {"force_channels": channels})
        await message.reply("✅ Force Subscribe added. Make the bot admin in that channel.")
    except Exception as e:
        await message.reply("❌ Cannot access that channel. Make the bot admin first.")


@Client.on_message(filters.command("caption") & filters.private)
async def caption(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2 or message.text.split(None, 1)[1].lower() == "off":
        save(client, {"custom_caption": None}); return await message.reply("✅ Custom caption disabled.")
    save(client, {"custom_caption": message.text.split(None, 1)[1]})
    await message.reply("✅ Custom caption saved. Variables: {file_name}, {file_size}, {file_caption}")


@Client.on_message(filters.command("button") & filters.private)
async def button(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2 or message.command[1].lower() == "off":
        save(client, {"custom_buttons": []}); return await message.reply("✅ Custom buttons cleared.")
    raw = message.text.split(None, 1)[1]
    if " - " not in raw:
        return await message.reply("Usage: <code>/button Text - https://example.com</code>")
    text, url = [x.strip() for x in raw.split(" - ", 1)]
    if not (url.startswith("https://") or url.startswith("http://")):
        return await message.reply("❌ Button URL must start with http:// or https://")
    buttons = list(bot_record(client).get("custom_buttons", []))
    buttons.append({"text": text[:64], "url": url})
    save(client, {"custom_buttons": buttons})
    await message.reply("✅ Custom button added.")


@Client.on_message(filters.command("protect") & filters.private)
async def protect(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    value = len(message.command) > 1 and message.command[1].lower() in ("on", "1", "yes", "true")
    save(client, {"protect_content": value})
    await message.reply("🔐 Protect Content: <b>%s</b>" % ("ON" if value else "OFF"))


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener_settings(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    user = await get_user(message.from_user.id)
    await message.reply("🔗 <b>Shortener</b>\nAPI: <code>%s</code>\nSite: <code>%s</code>\n\nUse /api KEY and /base_site example.com" % (user.get("shortener_api") or "Not set", user.get("base_site") or "Not set"))


@Client.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],[InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]])
    await message.reply("👑 <b>Owner Panel</b>", reply_markup=kb)


@Client.on_callback_query(filters.regex(r"^admin_(settings|stats|broadcast|shortener)$"))
async def admin_callback(client, query):
    if not owner_only(client, query.from_user.id): return await query.answer("Owner only.", show_alert=True)
    action = query.data.split("_", 1)[1]; d = bot_record(client)
    if action == "stats": text = "📊 <b>Users:</b> <code>%s</code>" % await clonedb.total_users_count(client.me.id)
    elif action == "shortener":
        u = await get_user(query.from_user.id); text = "🔗 API: <code>%s</code>\nSite: <code>%s</code>" % (u.get("shortener_api") or "Not set", u.get("base_site") or "Not set")
    elif action == "broadcast": text = "📢 Reply to a message and use <code>/broadcast</code>"
    else: text = "⚙️ Force Join: %s\nCaption: %s\nButtons: %s\nProtect: %s" % (len(d.get("force_channels", [])), "ON" if d.get("custom_caption") else "OFF", len(d.get("custom_buttons", [])), "ON" if d.get("protect_content") else "OFF")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]))


@Client.on_callback_query(filters.regex(r"^admin_back$"))
async def admin_back(client, query):
    if not owner_only(client, query.from_user.id): return await query.answer("Owner only.", show_alert=True)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],[InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]])
    await query.message.edit_text("👑 <b>Owner Panel</b>", reply_markup=kb)


@Client.on_message(filters.command("stats") & filters.private)
async def stats(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply("📊 <b>Users:</b> <code>%s</code>" % await clonedb.total_users_count(client.me.id))


@Client.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if not message.reply_to_message: return await message.reply("Reply to a message and use <code>/broadcast</code>.")
    sent = failed = 0
    async for u in clonedb.get_all_users(client.me.id):
        try: await message.reply_to_message.copy(u["user_id"]); sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
    await message.reply("📢 Done\nSent: %s\nFailed: %s" % (sent, failed))


@Client.on_message(filters.command(["custom_batch", "special_link", "universal_link"]) & filters.private)
async def advanced_links(client, message):
    if not message.reply_to_message: return await message.reply("Reply to a supported file first.")
    cmd = message.command[0].lower()
    if cmd == "custom_batch": return await message.reply("Use <code>/batch N</code> for consecutive files.")
    if cmd == "special_link": return await message.reply("Use <code>/link</code> with Protect enabled for protected delivery.")
    return await message.reply("Use <code>/link</code> for this clone's universal file link.")


@Client.on_message(filters.command("ban") & filters.private)
async def ban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit(): return await message.reply("Usage: /ban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": True}}, upsert=True); await message.reply("🚫 User banned.")


@Client.on_message(filters.command("unban") & filters.private)
async def unban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit(): return await message.reply("Usage: /unban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": False}}, upsert=True); await message.reply("✅ User unbanned.")
