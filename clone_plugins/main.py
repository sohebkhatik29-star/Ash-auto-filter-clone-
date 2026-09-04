import asyncio
import base64
import json
import os
import re
import tempfile

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait

from config import LOG_CHANNEL, AUTO_DELETE_MODE, AUTO_DELETE_TIME
from plugins.clone import mongo_db
from clone_plugins.dbusers import clonedb


def owner_id_for(bot_id):
    row = mongo_db.bots.find_one({"bot_id": bot_id})
    return int(row["user_id"]) if row and row.get("user_id") else None


def is_owner(message, bot_id):
    return bool(message.from_user and owner_id_for(bot_id) == message.from_user.id)


def settings(bot_id):
    return mongo_db.clone_settings.find_one({"bot_id": bot_id}) or {
        "bot_id": bot_id,
        "shortener_api": None,
        "base_site": None,
        "auto_delete": AUTO_DELETE_TIME,
        "auto_delete_mode": AUTO_DELETE_MODE,
    }


def save_settings(bot_id, **values):
    mongo_db.clone_settings.update_one({"bot_id": bot_id}, {"$set": values}, upsert=True)


def banned(bot_id, user_id):
    return bool(mongo_db.clone_bans.find_one({"bot_id": bot_id, "user_id": int(user_id)}))


async def share_link(client, message):
    if not message.reply_to_message:
        await message.reply_text("Reply to a file/message with /link or /genlink.")
        return None
    post = await message.reply_to_message.copy(LOG_CHANNEL)
    token = base64.urlsafe_b64encode(f"file_{post.id}".encode()).decode().rstrip("=")
    me = await client.get_me()
    return f"https://t.me/{me.username}?start={token}"


async def send_share_result(client, message):
    link = await share_link(client, message)
    if not link:
        return
    s = settings((await client.get_me()).id)
    if s.get("base_site") and s.get("shortener_api"):
        try:
            import requests
            r = requests.get(
                f"https://{s['base_site']}/api",
                params={"api": s["shortener_api"], "url": link},
                timeout=15,
            )
            link = r.json().get("shortenedUrl") or link
        except Exception:
            pass
    await message.reply_text(f"<b>🔗 Shareable link:</b>\n{link}")


async def delete_later(message, seconds):
    await asyncio.sleep(max(1, seconds))
    try:
        await message.delete()
    except Exception:
        pass


@Client.on_message(filters.command("start") & filters.private)
async def clone_start(client, message):
    me = await client.get_me()
    if banned(me.id, message.from_user.id):
        return await message.reply_text("⛔ You are banned from this bot.")
    await clonedb.add_user(me.id, message.from_user.id)
    if len(message.command) < 2:
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 HELP", callback_data="chelp")],
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="csettings"), InlineKeyboardButton("📊 STATS", callback_data="cstats")],
        ])
        return await message.reply_text(
            f"<b>👋 Hello {message.from_user.first_name}!</b>\n\n"
            f"I am <b>{me.first_name}</b>, an advanced file-store and link bot.\n\n"
            "Use /help to see all available commands.",
            reply_markup=buttons,
        )

    token = message.command[1]
    try:
        if token.startswith("BATCH-"):
            pad = "=" * (-len(token[6:]) % 4)
            msg_id = int(base64.urlsafe_b64decode(token[6:] + pad).decode())
            index = await client.get_messages(LOG_CHANNEL, msg_id)
            if not index or index.empty or not index.document:
                return await message.reply_text("Batch link not found.")
            path = await client.download_media(index, in_memory=False)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                count = 0
                for item in items:
                    stored = await client.get_messages(item["channel_id"], item["msg_id"])
                    if stored and not stored.empty:
                        sent = await stored.copy(message.chat.id)
                        count += 1
                        s = settings(me.id)
                        if s.get("auto_delete_mode"):
                            asyncio.create_task(delete_later(sent, int(s.get("auto_delete") or AUTO_DELETE_TIME)))
                return await message.reply_text(f"✅ Delivered <code>{count}</code> stored messages.")
            finally:
                try: os.remove(path)
                except OSError: pass

        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode()
        if raw.startswith("file_"):
            msg_id = int(raw.split("_", 1)[1])
            stored = await client.get_messages(LOG_CHANNEL, msg_id)
            if not stored or stored.empty:
                return await message.reply_text("File not found or expired.")
            sent = await stored.copy(message.chat.id)
            s = settings(me.id)
            if s.get("auto_delete_mode"):
                asyncio.create_task(delete_later(sent, int(s.get("auto_delete") or AUTO_DELETE_TIME)))
            return
        await message.reply_text("Invalid link payload.")
    except Exception as e:
        await message.reply_text(f"Unable to open this link: <code>{e}</code>")


@Client.on_message(filters.command(["link", "genlink"]) & filters.private)
async def clone_link(client, message):
    if banned((await client.get_me()).id, message.from_user.id):
        return await message.reply_text("⛔ You are banned from this bot.")
    await send_share_result(client, message)



@Client.on_message(filters.command("api") & filters.private)
async def clone_api(client, message):
    me = await client.get_me()
    if not is_owner(message, me.id):
        return await message.reply_text("<b>⛔ Owner only.</b>")
    if len(message.command) == 1:
        return await message.reply_text(f"Current shortener API: <code>{settings(me.id).get('shortener_api') or 'None'}</code>")
    value = message.command[1]
    save_settings(me.id, shortener_api=None if value.lower() == "none" else value)
    await message.reply_text("✅ Shortener API updated successfully.")


@Client.on_message(filters.command("base_site") & filters.private)
async def clone_base_site(client, message):
    me = await client.get_me()
    if not is_owner(message, me.id):
        return await message.reply_text("<b>⛔ Owner only.</b>")
    if len(message.command) == 1:
        return await message.reply_text(f"Current shortener site: <code>{settings(me.id).get('base_site') or 'None'}</code>")
    value = message.command[1].replace("https://", "").replace("http://", "").rstrip("/")
    save_settings(me.id, base_site=None if value.lower() == "none" else value)
    await message.reply_text("✅ Shortener site updated successfully.")


@Client.on_message(filters.command("shortener") & filters.private)
async def clone_shortener(client, message):
    me = await client.get_me()
    if not is_owner(message, me.id):
        return await message.reply_text("<b>⛔ Owner only.</b>")
    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply_text("Use /shortener <URL> or reply to a message containing a URL.")
    url = message.command[1] if len(message.command) > 1 else (message.reply_to_message.text or "").strip()
    s = settings(me.id)
    if not s.get("base_site") or not s.get("shortener_api"):
        return await message.reply_text("Set /api and /base_site first.")
    try:
        import requests
        r = requests.get(f"https://{s['base_site']}/api", params={"api": s["shortener_api"], "url": url}, timeout=15)
        out = r.json().get("shortenedUrl")
        await message.reply_text(out or "Shortener did not return a link.")
    except Exception as e:
        await message.reply_text(f"Shortener error: <code>{e}</code>")


HELP = """<b>📚 Available Commands</b>\n\n/start - Check bot / open a stored link\n/link - Create a shareable link\n/genlink - Same as /link\n/batch - Store a range of channel messages\n/custom_batch - Create a custom link\n/special_link - Create a special link\n/universal_link - Create a universal link\n/shortener - Shorten a URL\n/settings - View settings\n/api - Set/view shortener API\n/base_site - Set/view shortener site\n/admin - Owner admin panel\n/stats - Bot statistics (owner)\n/broadcast - Broadcast (owner)\n/ban - Ban a user (owner)\n/unban - Unban a user (owner)"""


@Client.on_message(filters.command("help") & filters.private)
async def clone_help(client, message):
    await message.reply_text(HELP, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ SETTINGS", callback_data="csettings"), InlineKeyboardButton("📊 STATS", callback_data="cstats")]]))


@Client.on_message(filters.command("settings") & filters.private)
async def clone_settings_cmd(client, message):
    me = await client.get_me(); s = settings(me.id)
    await message.reply_text(f"<b>⚙️ Settings</b>\n\nAPI: <code>{s.get('shortener_api') or 'None'}</code>\nSite: <code>{s.get('base_site') or 'None'}</code>\nAuto delete: <code>{s.get('auto_delete_mode')}</code>\nDelete after: <code>{s.get('auto_delete')}s</code>")


@Client.on_message(filters.command(["admin", "stats", "broadcast", "ban", "unban"]) & filters.private)
async def clone_owner_commands(client, message):
    me = await client.get_me()
    if not is_owner(message, me.id):
        return await message.reply_text("<b>⛔ Owner only.</b>")
    command = message.command[0]
    if command == "admin":
        return await message.reply_text(
            "<b>⚙️ CLONE BOT ADMIN PANEL</b>\n\nChoose an option:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Statistics", callback_data="cstats"), InlineKeyboardButton("🤖 Bot Info", callback_data="cinfo")],
                [InlineKeyboardButton("📣 Broadcast", callback_data="cbroadcast")],
            ]),
        )
    if command == "stats":
        return await message.reply_text(f"<b>📊 Statistics</b>\n\n👥 Users: <code>{await clonedb.total_users_count(me.id)}</code>\n🤖 @{me.username}")
    if command == "broadcast":
        if not message.reply_to_message:
            return await message.reply_text("Reply to the message you want to broadcast and send /broadcast.")
        ok = fail = 0
        async for u in await clonedb.get_all_users(me.id):
            try:
                if banned(me.id, int(u["user_id"])):
                    continue
                await message.reply_to_message.copy(int(u["user_id"]))
                ok += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                fail += 1
        return await message.reply_text(f"Broadcast complete.\n✅ {ok}\n❌ {fail}")
    if len(message.command) < 2:
        return await message.reply_text(f"Use /{command} <user_id>")
    uid = int(message.command[1])
    if command == "ban":
        from clone_plugins.ban_manager import ban_user
        await ban_user(client, uid)
        return await message.reply_text("🚫 User banned.")
    from clone_plugins.ban_manager import unban_user
    await unban_user(client, uid)
    return await message.reply_text("✅ User unbanned.")

@Client.on_callback_query(filters.regex(r"^c(hep|settings|stats|info|broadcast)$"))
async def clone_callbacks(client, query):
    me = await client.get_me()
    if query.data == "chelp":
        await query.answer(); return await query.message.edit_text(HELP)
    if query.data == "csettings":
        s = settings(me.id); await query.answer(); return await query.message.edit_text(f"<b>⚙️ Settings</b>\n\nAPI: <code>{s.get('shortener_api') or 'None'}</code>\nSite: <code>{s.get('base_site') or 'None'}</code>\nAuto delete: <code>{s.get('auto_delete_mode')}</code>\nDelete after: <code>{s.get('auto_delete')}s</code>")
    if not is_owner(query, me.id):
        await query.answer("Owner only", show_alert=True); return
    if query.data == "cstats":
        await query.answer(); return await query.message.edit_text(f"<b>📊 Statistics</b>\n\n👥 Users: <code>{await clonedb.total_users_count(me.id)}</code>")
    if query.data == "cinfo":
        await query.answer(); return await query.message.edit_text(f"<b>🤖 Bot Info</b>\n\nName: <code>{me.first_name}</code>\nUsername: <code>@{me.username}</code>\nID: <code>{me.id}</code>")
    if query.data == "cbroadcast":
        await query.answer("Reply to a message and use /broadcast.", show_alert=True)
