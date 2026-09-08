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


def clone_user_commands():
    return [
        BotCommand("start", "Check i am alive"),
    ]


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
    # Set default command menu for regular users so regular subscribers only see /start
    try:
        await client.set_bot_commands(clone_user_commands())
    except Exception:
        pass

    # Gather all authorized user IDs (clone owner, clone admins, master admins)
    auth_uids = set()
    if owner_id:
        try:
            auth_uids.add(int(owner_id))
        except Exception:
            pass

    try:
        rec = None
        if mongo_db is not None:
            b_id = getattr(client, "me", None) and client.me.id
            if b_id:
                rec = mongo_db.bots.find_one({"$or": [{"bot_id": int(b_id)}, {"bot_id": str(b_id)}]})
        if rec:
            rec_uid = rec.get("user_id")
            if rec_uid:
                try:
                    auth_uids.add(int(rec_uid))
                except Exception:
                    pass
            adms = rec.get("admins", [])
            if isinstance(adms, dict):
                adms = list(adms.values())
            for a in adms:
                if isinstance(a, dict) and a.get("user_id"):
                    try:
                        auth_uids.add(int(a["user_id"]))
                    except Exception:
                        pass
                elif str(a).isdigit():
                    try:
                        auth_uids.add(int(a))
                    except Exception:
                        pass
            for m in rec.get("moderators", []):
                if str(m).isdigit():
                    try:
                        auth_uids.add(int(m))
                    except Exception:
                        pass
    except Exception:
        pass

    try:
        from config import ADMINS
        for a in ADMINS:
            if str(a).strip().lstrip("-").isdigit():
                try:
                    auth_uids.add(int(a))
                except Exception:
                    pass
        if mongo_db is not None:
            for ma in mongo_db.master_admins.find():
                if ma.get("user_id"):
                    try:
                        auth_uids.add(int(ma["user_id"]))
                    except Exception:
                        pass
    except Exception:
        pass

    cmds = clone_commands(True)
    for uid in auth_uids:
        try:
            await client.set_bot_commands(cmds, scope=BotCommandScopeChat(chat_id=int(uid)))
        except Exception:
            pass


def register_clone_handlers(client):
    from clone_plugins.runtime_register import register_clone_handlers as _register
    _register(client)


@Client.on_message(filters.command(["clone", "clones", "my_clones"]) & filters.private)
async def clone(client, message):
    from plugins.master_settings import send_manage_clones
    return await send_manage_clones(client, message)


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

