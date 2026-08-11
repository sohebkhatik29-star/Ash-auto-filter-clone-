# ASH FILE STORE & CLONE MANAGER - advanced clone features
import time
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from clone_plugins.users_api import get_user, update_user_info
from plugins.clone import mongo_db
from config import CLONE_MODE


def bot_owner(client):
    doc = mongo_db.bots.find_one({"bot_id": client.me.id})
    return int(doc["user_id"]) if doc and doc.get("user_id") else None


def owner_only(client, user_id):
    return bot_owner(client) == int(user_id)


async def force_channels(client):
    doc = mongo_db.settings.find_one({"bot_id": client.me.id}) or {}
    return doc.get("force_channels", [])


@Client.on_message(filters.command("start") & filters.private, group=-10)
async def force_sub_check(client, message):
    if len(message.command) < 2 or not CLONE_MODE:
        return
    channels = await force_channels(client)
    if not channels:
        return
    not_joined = []
    for channel in channels:
        try:
            member = await client.get_chat_member(channel, message.from_user.id)
            if str(member.status) in ("left", "kicked"):
                chat = await client.get_chat(channel)
                invite = getattr(chat, "invite_link", None) or f"https://t.me/{str(channel).lstrip('@')}"
                not_joined.append((chat.title or str(channel), invite))
        except Exception:
            not_joined.append((str(channel), None))
    if not_joined:
        buttons = []
        for title, invite in not_joined:
            if invite:
                buttons.append([InlineKeyboardButton(f"📢 Join {title}", url=invite)])
        buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="check_force")])
        await message.reply_text(
            "<b>🔐 Please join the required channel(s) first.</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        raise StopPropagation


@Client.on_callback_query(filters.regex("^check_force$"))
async def check_force_callback(client, query):
    channels = await force_channels(client)
    missing = []
    for channel in channels:
        try:
            member = await client.get_chat_member(channel, query.from_user.id)
            if str(member.status) in ("left", "kicked"):
                missing.append(channel)
        except Exception:
            missing.append(channel)
    if missing:
        return await query.answer("❌ You have not joined all required channels.", show_alert=True)
    await query.answer("✅ Verification successful!", show_alert=True)
    await query.message.delete()


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener_settings(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    user = await get_user(message.from_user.id)
    await message.reply(
        "<b>🔗 Shortener</b>\n\n"
        f"API: <code>{user.get('shortener_api') or 'Not set'}</code>\n"
        f"Site: <code>{user.get('base_site') or 'Not set'}</code>\n\n"
        "Set with /api and /base_site."
    )


@Client.on_message(filters.command(["custom_batch", "special_link", "universal_link"]) & filters.private)
async def advanced_link_commands(client, message):
    """Provide safe aliases until a channel-backed multi-message store is configured."""
    cmd = message.command[0].lower()
    if cmd == "custom_batch":
        return await message.reply("Reply to the first file and use <code>/batch N</code> to create a batch.\nCustom batch controls are stored in clone settings.")
    if cmd == "special_link":
        return await message.reply("Reply to a file and use <code>/link</code>. Special-link protection is handled by the clone settings.")
    await message.reply("Reply to a file and use <code>/link</code>. Universal delivery uses this clone's own bot link.")


@Client.on_message(filters.command("stats") & filters.private)
async def stats(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    me = await client.get_me()
    count = await clonedb.total_users_count(me.id)
    await message.reply(f"<b>📊 Clone Statistics</b>\n\nUsers: <code>{count}</code>")


@Client.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    await message.reply(
        "<b>👑 Owner Panel</b>\n\n"
        "/stats - User statistics\n"
        "/settings - Clone settings\n"
        "/force_sub - Add force-join channel\n"
        "/caption - Set custom caption\n"
        "/button - Add custom button\n"
        "/broadcast - Broadcast to clone users"
    )


@Client.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    if not owner_only(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if not message.reply_to_message:
        return await message.reply("Reply to the message you want to broadcast and use /broadcast.")
    me = await client.get_me()
    sent = failed = 0
    users = clonedb.get_all_users(me.id)
    async for user in users:
        try:
            await message.reply_to_message.copy(user["user_id"])
            sent += 1
        except Exception:
            failed += 1
    await message.reply(f"<b>Broadcast complete.</b>\nSent: {sent}\nFailed: {failed}")
