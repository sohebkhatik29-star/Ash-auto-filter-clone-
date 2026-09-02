import re
import logging
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeChat
from config import API_ID, API_HASH, DB_URI, CLONE_MODE

try:
    import clone_plugins.master_manager
except Exception:
    logging.exception("Unable to load master clone manager")

mongo_client = MongoClient(DB_URI) if DB_URI else None
mongo_db = mongo_client["ash_clone_bots"] if mongo_client else None

CLONES = {}

def get_clone_client(bot_id):
    if not bot_id:
        return None
    try:
        bid = int(bot_id)
        if bid in CLONES:
            return CLONES[bid]
    except Exception:
        pass
    try:
        for k, v in CLONES.items():
            if str(k) == str(bot_id):
                return v
    except Exception:
        pass
    return None

def set_clone_client(bot_id, client):
    try:
        CLONES[int(bot_id)] = client
        CLONES[str(bot_id)] = client
    except Exception:
        pass

# Focused clone-manager UI fix. This is intentionally imported after mongo_db
# exists so it can safely access the clone database and register its handlers.
try:
    import clone_plugins.clone_manager_fix
except Exception:
    logging.exception("Unable to load focused clone manager fix")


def clone_commands(include_owner=False):
    base_commands = [
        BotCommand("start", "Check i am alive"),
        BotCommand("genlink", "To store a single message or file"),
        BotCommand("batch", "To store mutiple messages from a channel"),
        BotCommand("custom_batch", "To store multiple random messages"),
        BotCommand("special_link", "store multiple messages and get an editable link (owner can edit)"),
        BotCommand("universal_link", "stores multiple messages that can be accessed from any bot"),
        BotCommand("shortener", "To shorten any shareable links"),
        BotCommand("settings", "Customize Your settings as your need"),
    ]
    if include_owner:
        return base_commands + [
            BotCommand("broadcast", "Broadcast a messages to users (moderators only)"),
            BotCommand("an_broadcast", "Unpin broadcast messages from users"),
            BotCommand("ban", "Ban a user (moderators only)"),
            BotCommand("unban", "Unban a user (moderators only)"),
        ]
    return base_commands


async def set_clone_menu(client, owner_id=None):
    try:
        await client.set_bot_commands(clone_commands(False))
    except Exception:
        pass
    if owner_id:
        try:
            await client.set_bot_commands(clone_commands(True), scope=BotCommandScopeChat(chat_id=int(owner_id)))
        except Exception:
            logging.exception("Unable to set owner command menu")


def register_clone_handlers(client):
    from clone_plugins.runtime_register import register_clone_handlers as _register
    _register(client)


@Client.on_message(filters.command("clone") & filters.private)
async def clone(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    if not CLONE_MODE or mongo_db is None:
        return await message.reply_text("Clone mode is disabled or database is not configured.")

    from clone_plugins.master_manager import manage_clones_markup
    text = (
        "👑 <b>CLONE MENU</b>\n\n"
        "<i>\" WELCOME TO YOUR CLONE BOT MANAGEMENT HUB! CUSTOMIZE YOUR BOT SETTINGS OR MANAGE ITS STATUS USING THE OPTIONS BELOW. \"</i>\n\n"
        "⚙️ <b>QUICK COMMANDS</b>\n\n"
        "🚀 /activate - ACTIVATE YOUR CLONE BOT\n"
        "🗑️ /delete - PERMANENTLY DELETE YOUR CLONE BOT\n\n"
        "🎨 <b>BOT CUSTOMIZATION</b>\n\n"
        "✨ <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
    )
    return await message.reply_text(
        text,
        reply_markup=manage_clones_markup(message.from_user.id, back_cb="settings_back", is_clone=False)
    )


@Client.on_message(filters.command("deletecloned") & filters.private)
async def delete_cloned_bot(client, message):
    me = client.me or (await client.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    if not CLONE_MODE or mongo_db is None:
        return
    token_msg = await client.ask(message.chat.id, "<b>Send the bot token to delete its record.</b>")
    match = re.search(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', token_msg.text or '', re.IGNORECASE)
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
        token = bot.get("token") or bot.get("bot_token")
        if not token:
            logging.warning("Skipping clone %s: database record has no token field", bot.get("bot_id") or bot.get("username") or "unknown")
            continue
        try:
            vj = Client(token, API_ID, API_HASH, bot_token=token, plugins={})
            await vj.start()
            CLONES[int(vj.me.id)] = vj
            register_clone_handlers(vj)
            await set_clone_menu(vj, bot.get("user_id"))
            logging.info("Clone started: @%s", bot.get("username"))
            log_ch = bot.get("log_channel")
            if log_ch:
                try:
                    await vj.send_message(chat_id=int(log_ch), text=f"🤖 @{vj.me.username} IS RESTARTED ✅")
                except Exception:
                    pass
        except Exception:
            logging.exception("Unable to restart clone @%s", bot.get("username"))

