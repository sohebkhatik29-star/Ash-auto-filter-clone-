# © Telegram: @movies_1780
# ASH FILE STORE & CLONE MANAGER — per-clone owner settings

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from config import CLONE_DB_URI

_client = AsyncIOMotorClient(CLONE_DB_URI) if CLONE_DB_URI else None
_db = _client["ash_clone_bots"] if _client else None
settings = _db["settings"] if _db else None
bots = _db["bots"] if _db else None

DEFAULTS = {"force_channels": [], "custom_caption": None, "custom_buttons": [], "protect_content": False}

async def _owner(client):
    if bots is None:
        return None
    doc = await bots.find_one({"bot_id": client.me.id})
    return int(doc["user_id"]) if doc and doc.get("user_id") is not None else None

async def is_owner(client, user_id):
    return await _owner(client) == int(user_id)

async def get_settings(client):
    bot_id = client.me.id
    if settings is None:
        return {"bot_id": bot_id, **DEFAULTS}
    doc = await settings.find_one({"bot_id": bot_id})
    if not doc:
        doc = {"bot_id": bot_id, **DEFAULTS}
        await settings.insert_one(doc)
    return doc

async def save_settings(client, values):
    bot_id = client.me.id
    if settings is not None:
        await settings.update_one({"bot_id": bot_id}, {"$set": values}, upsert=True)
    # Delivery code reads the clone record, so keep both documents synchronized.
    if bots is not None:
        await bots.update_one({"bot_id": bot_id}, {"$set": values}, upsert=True)

@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client, message):
    if not await is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    s = await get_settings(client)
    await message.reply_text(
        "⚙️ <b>Clone Settings</b>\n\n"
        f"Force Join: <code>{len(s.get('force_channels', []))}</code>\n"
        f"Caption: <code>{'ON' if s.get('custom_caption') else 'OFF'}</code>\n"
        f"Custom Buttons: <code>{len(s.get('custom_buttons', []))}</code>\n"
        f"Protect Content: <code>{'ON' if s.get('protect_content') else 'OFF'}</code>"
    )

@Client.on_message(filters.command("force_sub") & filters.private)
async def force_sub_cmd(client, message):
    if not await is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    if len(message.command) != 2:
        return await message.reply_text("Usage: <code>/force_sub CHANNEL_ID</code>")
    s = await get_settings(client)
    channels = list(s.get("force_channels", []))
    value = message.command[1].strip()
    if value not in channels:
        channels.append(value)
    await save_settings(client, {"force_channels": channels})
    await message.reply_text("✅ Force-join channel saved.")

@Client.on_message(filters.command("caption") & filters.private)
async def caption_cmd(client, message):
    if not await is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/caption YOUR CAPTION</code>")
    await save_settings(client, {"custom_caption": message.text.split(None, 1)[1]})
    await message.reply_text("✅ Custom caption saved.")

@Client.on_message(filters.command("button") & filters.private)
async def button_cmd(client, message):
    if not await is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3:
        return await message.reply_text("Usage: <code>/button ButtonText https://example.com</code>")
    text, url = parts[1], parts[2]
    if not url.startswith(("http://", "https://")):
        return await message.reply_text("❌ Invalid button URL.")
    s = await get_settings(client)
    buttons = list(s.get("custom_buttons", []))
    buttons.append({"text": text, "url": url})
    await save_settings(client, {"custom_buttons": buttons})
    await message.reply_text("✅ Custom button saved.")

@Client.on_message(filters.command("protect") & filters.private)
async def protect_cmd(client, message):
    if not await is_owner(client, message.from_user.id):
        return await message.reply_text("❌ Owner only.")
    if len(message.command) != 2 or message.command[1].lower() not in ("on", "off"):
        return await message.reply_text("Usage: <code>/protect on</code> or <code>/protect off</code>")
    enabled = message.command[1].lower() == "on"
    await save_settings(client, {"protect_content": enabled})
    await message.reply_text(f"✅ Protect Content: <b>{'ON' if enabled else 'OFF'}</b>")
