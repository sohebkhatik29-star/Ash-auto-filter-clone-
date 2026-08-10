# Clone-owner settings: force join, custom captions and custom buttons.
# Settings are isolated per cloned bot.
from pymongo import MongoClient
from pyrogram import Client, filters
from config import DB_URI, CLONE_MODE

mongo_client = MongoClient(DB_URI)
db = mongo_client["ash_clone_bots"]
settings = db["settings"]


def owner_id_for(client):
    doc = db.bots.find_one({"bot_id": client.me.id})
    return doc.get("user_id") if doc else None


def is_owner(client, user_id):
    return owner_id_for(client) == user_id


def get_settings(client):
    bot_id = client.me.id
    return settings.find_one({"bot_id": bot_id}) or {"bot_id": bot_id}


@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client, message):
    if not CLONE_MODE or not is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    s = get_settings(client)
    force = s.get("force_channels", [])
    caption = s.get("caption", "Default caption")
    buttons = s.get("buttons", [])
    await message.reply_text(
        "⚙️ <b>Clone Settings</b>\n\n"
        f"Force Join: <code>{len(force)}</code> channel(s)\n"
        f"Caption: <code>{caption[:100]}</code>\n"
        f"Custom Buttons: <code>{len(buttons)}</code>"
    )


@Client.on_message(filters.command("force_sub") & filters.private)
async def force_sub_cmd(client, message):
    if not is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await message.reply_text("Usage: <code>/force_sub -1001234567890</code>")
    channel = parts[1].strip()
    settings.update_one({"bot_id": client.me.id}, {"$addToSet": {"force_channels": channel}}, upsert=True)
    await message.reply_text("✅ Force-join channel saved.")


@Client.on_message(filters.command("caption") & filters.private)
async def caption_cmd(client, message):
    if not is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    caption = (message.text or "").split(maxsplit=1)
    if len(caption) != 2:
        return await message.reply_text("Usage: <code>/caption Your custom caption</code>")
    settings.update_one({"bot_id": client.me.id}, {"$set": {"caption": caption[1]}}, upsert=True)
    await message.reply_text("✅ Custom caption saved.")


@Client.on_message(filters.command("button") & filters.private)
async def button_cmd(client, message):
    if not is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3:
        return await message.reply_text("Usage: <code>/button Button Text https://example.com</code>")
    text, url = parts[1], parts[2]
    if not (url.startswith("https://") or url.startswith("http://")):
        return await message.reply_text("❌ Button URL must start with http:// or https://")
    settings.update_one({"bot_id": client.me.id}, {"$push": {"buttons": {"text": text, "url": url}}}, upsert=True)
    await message.reply_text("✅ Custom button saved.")
