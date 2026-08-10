import re
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeChat
from config import API_ID, API_HASH, DB_URI, CLONE_MODE

mongo_client = MongoClient(DB_URI)
mongo_db = mongo_client["ash_clone_bots"]


def clone_commands(include_owner=False):
    commands = [
        BotCommand("start", "Check bot / open stored link"),
        BotCommand("help", "Show all commands"),
        BotCommand("link", "Create a shareable file link"),
        BotCommand("genlink", "Create a shareable file link"),
        BotCommand("batch", "Store a range of channel messages"),
        BotCommand("custom_batch", "Create a custom link"),
        BotCommand("special_link", "Create a special link"),
        BotCommand("universal_link", "Create a universal link"),
        BotCommand("shortener", "Shorten a URL"),
        BotCommand("settings", "View bot settings"),
        BotCommand("api", "Set or view shortener API"),
        BotCommand("base_site", "Set or view shortener site"),
    ]
    if include_owner:
        commands += [
            BotCommand("admin", "Open owner admin panel"),
            BotCommand("stats", "Show bot statistics"),
            BotCommand("broadcast", "Broadcast a message"),
            BotCommand("ban", "Ban a user"),
            BotCommand("unban", "Unban a user"),
        ]
    return commands


async def set_clone_menu(client, owner_id=None):
    try:
        await client.set_bot_commands(clone_commands())
        if owner_id:
            await client.set_bot_commands(
                clone_commands(include_owner=True),
                scope=BotCommandScopeChat(chat_id=int(owner_id)),
            )
    except Exception:
        pass


@Client.on_message(filters.command("clone") & filters.private)
async def clone(client, message):
    if not CLONE_MODE:
        return
    techvj = await client.ask(
        message.chat.id,
        "<b>1) Send <code>/newbot</code> to @BotFather\n"
        "2) Give a name.\n3) Give a username.\n"
        "4) Copy the bot token message.\n5) Forward it to me.\n\n"
        "/cancel - cancel this process.</b>",
    )
    if (techvj.text or "").strip() == "/cancel":
        await techvj.delete()
        return await message.reply_text("<b>Cancelled 🚫</b>")
    if not techvj.forward_from or techvj.forward_from.id != 93372553:
        return await message.reply_text("<b>Please forward the token message from BotFather.</b>")
    try:
        bot_token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", techvj.text or "")[0]
    except Exception:
        return await message.reply_text("<b>Could not read the bot token.</b>")

    user_id = message.from_user.id
    msg = await message.reply_text("<b>👨‍💻 Creating your clone...</b>")
    try:
        vj = Client(
            bot_token,
            API_ID,
            API_HASH,
            bot_token=bot_token,
            plugins={"root": "clone_plugins"},
        )
        await vj.start()
        bot = await vj.get_me()
        details = {
            "bot_id": bot.id,
            "is_bot": True,
            "user_id": user_id,
            "name": bot.first_name,
            "token": bot_token,
            "username": bot.username,
        }
        mongo_db.bots.update_one({"bot_id": bot.id}, {"$set": details}, upsert=True)
        await set_clone_menu(vj, user_id)
        await msg.edit_text(f"<b>✅ Successfully cloned: @{bot.username}</b>")
    except BaseException as e:
        await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>")


@Client.on_message(filters.command("deletecloned") & filters.private)
async def delete_cloned_bot(client, message):
    if not CLONE_MODE:
        return
    try:
        techvj = await client.ask(message.chat.id, "<b>Send the bot token to delete its record.</b>")
        token = re.findall(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', techvj.text or "", re.IGNORECASE)
        token = token[0] if token else None
        cloned_bot = mongo_db.bots.find_one({"token": token})
        if cloned_bot:
            mongo_db.bots.delete_one({"token": token})
            await message.reply_text("<b>🤖 Clone record removed.</b>")
        else:
            await message.reply_text("<b>⚠️ Token is not in the cloned list.</b>")
    except Exception as e:
        await message.reply_text(f"<b>Error:</b> <code>{e}</code>")


async def restart_bots():
    for bot in list(mongo_db.bots.find()):
        try:
            vj = Client(
                bot["token"],
                API_ID,
                API_HASH,
                bot_token=bot["token"],
                plugins={"root": "clone_plugins"},
            )
            await vj.start()
            await set_clone_menu(vj, bot.get("user_id"))
        except Exception:
            pass
