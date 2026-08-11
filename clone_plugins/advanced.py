# ASH FILE STORE & CLONE MANAGER - advanced clone features
import asyncio
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user
from plugins.clone import mongo_db
from config import CLONE_MODE


def bot_owner(client):
    if mongo_db is None:
        return None
    doc = mongo_db.bots.find_one({"bot_id": client.me.id})
    return int(doc["user_id"]) if doc and doc.get("user_id") else None


def owner_only(client, user_id):
    return bot_owner(client) == int(user_id)


def bot_record(client):
    if mongo_db is None:
        return {}
    return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}


def force_channels(client):
    return bot_record(client).get("force_channels", [])


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener_settings(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    user = await get_user(message.from_user.id)
    await message.reply("<b>🔗 Shortener</b>\n\nAPI: <code>%s</code>\nSite: <code>%s</code>\n\nSet with /api and /base_site." % (user.get("shortener_api") or "Not set", user.get("base_site") or "Not set"))


@Client.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]
    ])
    await message.reply("<b>👑 Owner Panel</b>", reply_markup=kb)


@Client.on_callback_query(filters.regex(r"^admin_(settings|stats|broadcast|shortener)$"))
async def admin_callback(client, query):
    if not owner_only(client, query.from_user.id):
        return await query.answer("Owner only.", show_alert=True)
    action = query.data.split("_", 1)[1]
    record = bot_record(client)
    if action == "stats":
        text = "📊 <b>Users:</b> <code>%s</code>" % await clonedb.total_users_count(client.me.id)
    elif action == "shortener":
        user = await get_user(query.from_user.id)
        text = "🔗 API: <code>%s</code>\nSite: <code>%s</code>" % (user.get("shortener_api") or "Not set", user.get("base_site") or "Not set")
    elif action == "broadcast":
        text = "📢 Reply to a message and use <code>/broadcast</code>"
    else:
        text = "⚙️ <b>Clone Settings</b>\n\nForce Join: %s\nCaption: %s\nButtons: %s\nProtect: %s" % (len(record.get("force_channels", [])), "ON" if record.get("custom_caption") else "OFF", len(record.get("custom_buttons", [])), "ON" if record.get("protect_content") else "OFF")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]))


@Client.on_callback_query(filters.regex(r"^admin_back$"))
async def admin_back(client, query):
    if not owner_only(client, query.from_user.id):
        return await query.answer("Owner only.", show_alert=True)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="admin_shortener")]
    ])
    await query.message.edit_text("<b>👑 Owner Panel</b>", reply_markup=kb)


@Client.on_message(filters.command("stats") & filters.private)
async def stats(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    await message.reply("<b>📊 Clone Statistics</b>\n\nUsers: <code>%s</code>" % await clonedb.total_users_count(client.me.id))


@Client.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if not message.reply_to_message:
        return await message.reply("Reply to the message you want to broadcast and use <code>/broadcast</code>.")
    sent = failed = 0
    async for user in clonedb.get_all_users(client.me.id):
        try:
            await message.reply_to_message.copy(user["user_id"])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.reply("<b>Broadcast complete.</b>\nSent: %s\nFailed: %s" % (sent, failed))


@Client.on_message(filters.command("ban") & filters.private)
async def ban(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit():
        return await message.reply("Usage: <code>/ban USER_ID</code>")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": True}}, upsert=True)
    await message.reply("🚫 User banned.")


@Client.on_message(filters.command("unban") & filters.private)
async def unban(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if len(message.command) != 2 or not message.command[1].isdigit():
        return await message.reply("Usage: <code>/unban USER_ID</code>")
    await clonedb.db[str(client.me.id)].update_one({"user_id": int(message.command[1])}, {"$set": {"banned": False}}, upsert=True)
    await message.reply("✅ User unbanned.")


@Client.on_message(filters.command(["custom_batch", "special_link", "universal_link"]) & filters.private)
async def advanced_links(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a supported file first.")
    cmd = message.command[0].lower()
    if cmd == "custom_batch":
        return await message.reply("Use <code>/batch N</code> for a batch of consecutive files.")
    if cmd == "special_link":
        return await message.reply("Use <code>/link</code> for a protected/shareable file link.")
    await message.reply("Use <code>/link</code> for this clone's universal file link.")
