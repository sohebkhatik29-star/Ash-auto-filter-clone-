import re
import logging
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeChat, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, DB_URI, CLONE_MODE, BOT_USERNAME

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
        old = CLONES.get(int(bot_id)) or CLONES.get(str(bot_id))
        if old and old != client:
            try:
                import asyncio
                asyncio.create_task(old.stop())
            except Exception:
                pass
        CLONES[int(bot_id)] = client
        CLONES[str(bot_id)] = client
    except Exception:
        pass

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
            BotCommand("addpost", "Send a post message to all users"),
            BotCommand("delpost", "Delete a sent post from all users"),
            BotCommand("delallpost", "Delete all posts sent to all users"),
            BotCommand("broadcast", "Broadcast a messages to users (moderators only)"),
            BotCommand("an_broadcast", "Unpin broadcast messages from users"),
            BotCommand("bin", "Ban a user (moderators only)"),
            BotCommand("unban", "Unban a user (moderators only)"),
        ]
    return base_commands


async def set_clone_menu(client, owner_id=None):
    try:
        await client.set_bot_commands(clone_user_commands())
    except Exception:
        pass

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
                        auth_uids.add(int(a.get("user_id")))
                    except Exception:
                        pass
                elif str(a).disgit():
                    try:
                        auth_uids.add(int(a))
                    except Exception:
                        pass
            mods = rec.get("moderators", [])
            if isinstance(mods, list):
                for m_id in mods:
                    if str(m_id).disgit():
                        try:
                            auth_uids.add(int(m_id))
                        except Exception:
                            pass
    except Exception:
        pass

    try:
        from config import ADMINS
        for a in ADMINS:
            if str(a).strip().lstrip("-").isdigit():
                auth_uids.add(int(a))
    except Exception:
        pass

    try:
        if mongo_db is not None:
            for ma in mongo_db.master_admins.find():
                mu = ma.get("user_id")
                if mu:
                    try:
                        auth_uids.add(int(mu))
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


@Client.on_message(filters.command(["activate", "activate_clone", "active"]) & filters.private)
async def activate_command(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or mongo_db is None:
        return

    bots = list(mongo_db.bots.find({"user_id": int(user_id)}))
    if not bots:
        return await message.reply_text(
            "❌ <b>You don't have any clone bot created yet!</b>\n\n<i>Use /clone command to create your own clone bot.</i>"
        )

    keyboard_rows = []
    for b in bots:
        uname = b.get("username") or f"bot_{b.get('bot_id', '')}"
        keyboard_rows.append([f"@{uname.lstrip('@')}"])
    keyboard_rows.append(["❌ Cancel"])

    reply_kb = ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True, one_time_keyboard=True)

    try:
        ans = await client.ask(
            chat_id=message.chat.id,
            text="🦹 <b>SELECT THE BOT YOU WANT TO ACTIVATE:</b>",
            reply_markup=reply_kb,
            timeout=120
        )
    except Exception:
        return await message.reply_text("❌ <b>Activation timed out.</b>", reply_markup=ReplyKeyboardRemove())

    if not ans or not ans.text:
        return await message.reply_text("❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())

    ans_text = str(ans.text).strip()
    if ans_text in ("❌ Cancel", "/cancel", "cancel", "Cancel"):
        return await message.reply_text("❌ <b>Activation cancelled.</b>", reply_markup=ReplyKeyboardRemove())

    clean_name = ans_text.lstrip("@").lower()
    target_bot = None
    for b in bots:
        b_uname = (b.get("username") or "").lstrip("@").lower()
        b_id_str = str(b.get("bot_id", ""))
        if clean_name == b_uname or clean_name == b_id_str:
            target_bot = b
            break

    if not target_bot:
        return await message.reply_text("❌ <b>INVALID BOT SELECTED</b>", reply_markup=ReplyKeyboardRemove())

    is_deactivated = bool(target_bot.get("deactivated", False))
    if not is_deactivated:
        return await message.reply_text("🚀 <b>YOUR BOT IS ALREADY ACTIVATED</b> 🚀", reply_markup=ReplyKeyboardRemove())

    mongo_db.bots.update_one({"_id": target_bot["_id"]}, {"$set": {"deactivated": False}})
    token = target_bot.get("token") or target_bot.get("bot_token")
    bid = target_bot.get("bot_id")
    if token:
        try:
            bot_prefix = bid or target_bot.get("username", "bot")
            vj = Client(f"clone_{user_id}_{bot_prefix}", API_ID, API_HASH, bot_token=token, plugins={})
            await vj.start()
            CLONES[int(vj.me.id)] = vj
            CLONES[str(vj.me.id)] = vj
            register_clone_handlers(vj)
            await set_clone_menu(vj, user_id)
        except Exception as e:
            logging.exception("Failed to start activated clone bot: %s", e)

    return await message.reply_text("🚀 <b>YOUR BOT HAS BEEN ACTIVATED SUCCESSFULLY</b> 🚀", reply_markup=ReplyKeyboardRemove())


@Client.on_message(filters.command(["delete", "deletecloned", "delbot", "delete_clone"]) & filters.private)
async def delete_cloned_bot(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or mongo_db is None:
        return

    bots = list(mongo_db.bots.find({'user_id': int(user_id)}))
    if not bots:
        return await message.reply_text(
            "❌ <b>You don't have any clone bot created yet!</b>"
        )

    keyboard_rows = []
    for b in bots:
        uname = b.get("username") or f"bot_{b.get('bot_id', '')}"
        keyboard_rows.append([f"@{uname.lstrip('@')}"])
    keyboard_rows.append(["❌ Cancel"])

    reply_kb = ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True, one_time_keyboard=True)

    try:
        ans = await client.ask(
            chat_id=message.chat.id,
            text="🎁 <b>SELECT THE BOT YOU WANT TO DELETE:</b>",
            reply_markup=reply_kb,
            timeout=120
        )
    except Exception:
        return await message.reply_text("❌ <b>Deletion timed out.</b>", reply_markup=ReplyKeyboardRemove())

    if not ans or not ans.text:
        return await message.reply_text("❌ <b>Process cancelled.</b>", reply_markup=ReplyKeyboardRemove())

    ans_text = str(ans.text).strip()
    if ans_text in ("❌ Cancel", "/cancel", "cancel", "Cancel"):
        return await message.reply_text("❌ <b>Deletion cancelled.</b>", reply_markup=ReplyKeyboardRemove())

    clean_name = ans_text.lstrip("@").lower()
    target_bot = None
    for b in bots:
        b_uname = (b.get("username") or "").lstrip("@").lower()
        b_id_str = str(b.get("bot_id", ""))
        if clean_name == b_uname or clean_name == b_id_str:
            target_bot = b
            break

    if not target_bot:
        return await message.reply_text("❌ <b>INVALID BOT SELECTED</b>", reply_markup=ReplyKeyboardRemove())

    bid = target_bot.get("bot_id")
    c = get_clone_client(bid)
    if c:
        try:
            await c.stop()
        except Exception:
            pass
        CLONES.pop(bid, None)
        CLONES.pop(str(bid), None)

    mongo_db.bots.delete_one({"_id": target_bot["_id"]})
    try:
        mongo_db.active_clone_edit.delete_many({"bot_id": bid})
    except Exception:
        pass

    return await message.reply_text("🗑️ <b>YOUR BOT HAS BEEN DELETED SUCCESSFULLY!</b>", reply_markup=ReplyKeyboardRemove())


async def restart_bots():
    if mongo_db is None:
        return
    for bot in list(mongo_db.bots.find()):
        if bot.get("deactivated") is True:
            continue
        token = bot.get("token") or bot.get("bot_token")
        if not token:
            logging.warning("Skipping clone %s: database record has no token field", bot.get("bot_id") or bot.get("username") or "unknown")
            continue
        try:
            bid = bot.get("bot_id")
            if bid and get_clone_client(bid):
                logging.info("Clone @%s is already running, skipping restart.", bot.get("username"))
                continue
            vj = Client(token, API_ID, API_HASH, bot_token=token, plugins={})
            await vj.start()
            existing = get_clone_client(vj.me.id)
            if existing and existing != vj:
                try:
                    await existing.stop()
                except Exception:
                    pass
            CLONES[int(vj.me.id)] = vj
            CLONES[str(vj.me.id)] = vj
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
