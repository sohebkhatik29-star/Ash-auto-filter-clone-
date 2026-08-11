# ASH FILE STORE & CLONE MANAGER - per-clone owner controls
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from plugins.clone import mongo_db


def owner(client, user_id):
    row = mongo_db.bots.find_one({"bot_id": client.me.id})
    return bool(row and int(row.get("user_id", 0)) == int(user_id))


def row(client):
    return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}


def save(client, values):
    mongo_db.bots.update_one({"bot_id": client.me.id}, {"$set": values}, upsert=True)


@Client.on_message(filters.command("force_sub") & filters.private)
async def force_sub(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if len(message.command) == 1:
        channels = row(client).get("force_channels", [])
        return await message.reply("<b>Force Subscribe</b>\n\n" + ("\n".join(map(str, channels)) if channels else "No channels added.") + "\n\n<code>/force_sub add @channel</code>\n<code>/force_sub remove @channel</code>\n<code>/force_sub off</code>")
    action = message.command[1].lower()
    channels = list(row(client).get("force_channels", []))
    if action == "off":
        save(client, {"force_channels": []})
        return await message.reply("✅ Force Subscribe disabled.")
    if len(message.command) < 3:
        return await message.reply("Usage: <code>/force_sub add @channel</code>")
    channel = message.command[2]
    if action == "add":
        if channel not in channels:
            channels.append(channel)
        save(client, {"force_channels": channels})
        return await message.reply("✅ Channel added. Make the clone bot an administrator there so membership can be checked.")
    if action == "remove":
        channels = [x for x in channels if str(x) != channel]
        save(client, {"force_channels": channels})
        return await message.reply("✅ Channel removed.")
    await message.reply("Usage: <code>/force_sub add @channel</code>")


@Client.on_message(filters.command("caption") & filters.private)
async def caption(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if len(message.command) == 1:
        return await message.reply("<b>Current caption:</b>\n" + (row(client).get("custom_caption") or "Default"))
    value = message.text.split(maxsplit=1)[1]
    if value.lower() == "off":
        save(client, {"custom_caption": None})
        return await message.reply("✅ Custom caption disabled.")
    save(client, {"custom_caption": value})
    await message.reply("✅ Custom caption saved.")


@Client.on_message(filters.command("button") & filters.private)
async def button(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/button Text | https://example.com</code>\nOr <code>/button off</code>")
    raw = message.text.split(maxsplit=1)[1]
    if raw.lower() == "off":
        save(client, {"custom_buttons": []})
        return await message.reply("✅ Custom buttons removed.")
    if "|" not in raw:
        return await message.reply("Use: <code>/button Button Text | https://example.com</code>")
    text, url = [x.strip() for x in raw.split("|", 1)]
    if not url.startswith(("http://", "https://")):
        return await message.reply("❌ Button URL must start with http:// or https://")
    buttons = list(row(client).get("custom_buttons", []))
    buttons.append({"text": text[:64], "url": url})
    save(client, {"custom_buttons": buttons})
    await message.reply("✅ Custom button saved.")


@Client.on_message(filters.command("settings") & filters.private)
async def settings(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    data = row(client)
    channels = data.get("force_channels", [])
    buttons = data.get("custom_buttons", [])
    text = (
        "<b>⚙️ Clone Settings</b>\n\n"
        f"Force Subscribe: <code>{len(channels)}</code> channel(s)\n"
        f"Custom Caption: <code>{'ON' if data.get('custom_caption') else 'OFF'}</code>\n"
        f"Custom Buttons: <code>{len(buttons)}</code>\n"
        f"Protect Content: <code>{'ON' if data.get('protect_content') else 'OFF'}</code>"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Force Subscribe", callback_data="settings_force")], [InlineKeyboardButton("Close", callback_data="close_data")]])
    await message.reply(text, reply_markup=markup)


@Client.on_message(filters.command("protect") & filters.private)
async def protect(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    value = len(message.command) > 1 and message.command[1].lower() in ("on", "yes", "true", "1")
    save(client, {"protect_content": value})
    await message.reply(f"✅ Protect Content {'enabled' if value else 'disabled'}.")


@Client.on_message(filters.command("shortener") & filters.private)
async def shortener(client, message):
    if not owner(client, message.from_user.id):
        return await message.reply("❌ Owner only.")
    data = row(client)
    await message.reply(
        "<b>🔗 Shortener</b>\n\n"
        f"API: <code>{data.get('shortener_api') or 'Not set'}</code>\n"
        f"Site: <code>{data.get('base_site') or 'Not set'}</code>\n\n"
        "Use /api KEY and /base_site example.com"
    )
