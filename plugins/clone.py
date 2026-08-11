import re
import logging
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeChat
from config import API_ID, API_HASH, DB_URI, CLONE_MODE

mongo_client = MongoClient(DB_URI) if DB_URI else None
mongo_db = mongo_client["ash_clone_bots"] if mongo_client else None


def clone_commands(include_owner=False):
    commands = [
        BotCommand("start", "Check bot / open stored link"), BotCommand("help", "Show all commands"),
        BotCommand("link", "Create a shareable file link"), BotCommand("genlink", "Create a shareable file link"),
        BotCommand("batch", "Create a batch link"), BotCommand("custom_batch", "Create a custom batch link"),
        BotCommand("special_link", "Create a special link"), BotCommand("universal_link", "Create a universal link"),
        BotCommand("shortener", "View shortener settings"), BotCommand("settings", "View clone settings"),
        BotCommand("api", "Set or view shortener API"), BotCommand("base_site", "Set or view shortener site"),
    ]
    if include_owner:
        commands += [BotCommand("admin", "Open owner admin panel"), BotCommand("stats", "Show bot statistics"),
                     BotCommand("broadcast", "Broadcast a message"), BotCommand("ban", "Ban a user"),
                     BotCommand("unban", "Unban a user"), BotCommand("force_sub", "Set Force Subscribe"),
                     BotCommand("caption", "Set Custom Caption"), BotCommand("button", "Add Custom Button"),
                     BotCommand("protect", "Protect Content on/off")]
    return commands


async def set_clone_menu(client, owner_id=None):
    await client.set_bot_commands(clone_commands())
    if owner_id:
        try:
            await client.set_bot_commands(clone_commands(True), scope=BotCommandScopeChat(chat_id=int(owner_id)))
        except Exception:
            logging.exception("Unable to set owner command menu")


def register_clone_handlers(client):
    """Load clone command handlers on this exact client instance."""
    from clone_plugins.commands import register as register_commands
    from clone_plugins.advanced import register as register_advanced
    register_commands(client)
    register_advanced(client)


@Client.on_message(filters.command("clone") & filters.private)
async def clone(client, message):
    if not CLONE_MODE or mongo_db is None:
        return await message.reply_text("Clone mode is disabled or database is not configured.")
    prompt = ("<b>1) Send <code>/newbot</code> to @BotFather\n2) Give a name.\n3) Give a username.\n"
              "4) Copy the bot token message.\n5) Copy/forward the token message to me.\n\n/cancel - cancel.</b>")
    token_msg = await client.ask(message.chat.id, prompt)
    if (token_msg.text or "").strip() == "/cancel":
        return await message.reply_text("<b>Cancelled 🚫</b>")
    if not token_msg.forward_from or token_msg.forward_from.id != 93372553:
        return await message.reply_text("<b>Please forward the token message from BotFather.</b>")
    match = re.search(r"\b(\d+:[A-Za-z0-9_-]+)\b", token_msg.text or "")
    if not match:
        return await message.reply_text("<b>Could not read the bot token.</b>")
    bot_token = match.group(1)
    msg = await message.reply_text("<b>👨‍💻 Creating your clone...</b>")
    try:
        # Do not use Pyrogram's plugin loader for clones. We register every
        # handler explicitly on this instance, which avoids silent plugin-load failures.
        vj = Client(bot_token, API_ID, API_HASH, bot_token=bot_token, plugins={})
        await vj.start()
        register_clone_handlers(vj)
        bot = await vj.get_me()
        mongo_db.bots.update_one({"bot_id": bot.id}, {"$set": {
            "bot_id": bot.id, "is_bot": True, "user_id": message.from_user.id,
            "name": bot.first_name, "token": bot_token, "username": bot.username,
            "force_channels": [], "custom_caption": None, "custom_buttons": [], "protect_content": False
        }}, upsert=True)
        await set_clone_menu(vj, message.from_user.id)
        await msg.edit_text(f"<b>✅ Successfully cloned: @{bot.username}</b>\n\nAll command handlers loaded.")
    except BaseException as e:
        logging.exception("Clone creation failed")
        await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>")


@Client.on_message(filters.command("deletecloned") & filters.private)
async def delete_cloned_bot(client, message):
    if not CLONE_MODE or mongo_db is None:
        return
    token_msg = await client.ask(message.chat.id, "<b>Send the bot token to delete its record.</b>")
    match = re.search(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', token_msg.text or "", re.IGNORECASE)
    token = match.group(0) if match else None
    if token and mongo_db.bots.find_one({"token": token}):
        mongo_db.bots.delete_one({"token": token})
        await message.reply_text("<b>🤖 Clone record removed.</b>")
    else:
        await message.reply_text("<b>⚠️ Token is not in the cloned list.</b>")


async def restart_bots():
    if mongo_db is None:
        return
    for bot in list(mongo_db.bots.find()):
        try:
            vj = Client(bot["token"], API_ID, API_HASH, bot_token=bot["token"], plugins={})
            await vj.start()
            register_clone_handlers(vj)
            await set_clone_menu(vj, bot.get("user_id"))
            logging.info("Clone started with all handlers: @%s", bot.get("username"))
        except Exception:
            logging.exception("Unable to restart clone")
