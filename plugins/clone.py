# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

import re
from pymongo import MongoClient
from Script import script
from pyrogram import Client, filters
from pyrogram.types import Message, BotCommand, BotCommandScopeChat
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid
from config import API_ID, API_HASH, DB_URI, DB_NAME, CLONE_MODE

mongo_client = MongoClient(DB_URI)
mongo_db = mongo_client["ash_clone_bots"]


def clone_commands(include_owner=False):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("link", "Create a shareable file link"),
        BotCommand("api", "Set or view shortener API"),
        BotCommand("base_site", "Set or view shortener site"),
    ]
    if include_owner:
        commands.append(BotCommand("broadcast", "Broadcast a message to users"))
    return commands


async def set_clone_menu(client, owner_id=None):
    try:
        await client.set_bot_commands(clone_commands())
        if owner_id:
            try:
                await client.set_bot_commands(
                    clone_commands(include_owner=True),
                    scope=BotCommandScopeChat(chat_id=int(owner_id)),
                )
            except Exception:
                pass
    except Exception:
        pass


@Client.on_message(filters.command("clone") & filters.private)
async def clone(client, message):
    if CLONE_MODE == False:
        return
    techvj = await client.ask(message.chat.id, "<b>1) sᴇɴᴅ <code>/newbot</code> ᴛᴏ @BotFather\n2) ɢɪᴠᴇ ᴀ ɴᴀᴍᴇ ꜰᴏʀ ʏᴏᴜʀ ʙᴏᴛ.\n3) ɢɪᴠᴇ ᴀ ᴜsᴇʀɴᴀᴍᴇ.\n4) ʏᴏᴜ ᴡɪʟʟ ɢᴇᴛ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ʏᴏᴜʀ ʙᴏᴛ ᴛᴏᴋᴇɴ.\n5) ꜰᴏʀᴡᴀʀᴅ ᴛʜᴀᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴍᴇ.\n\n/cancel - ᴄᴀɴᴄᴇʟ ᴛʜɪs ᴘʀᴏᴄᴇss.</b>")
    if techvj.text == '/cancel':
        await techvj.delete()
        return await message.reply('<b>ᴄᴀɴᴄᴇʟᴇᴅ ᴛʜɪs ᴘʀᴏᴄᴇss 🚫</b>')
    if techvj.forward_from and techvj.forward_from.id == 93372553:
        try:
            bot_token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", techvj.text)[0]
        except:
            return await message.reply('<b>sᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ 😕</b>')
    else:
        return await message.reply('<b>ɴᴏᴛ ꜰᴏʀᴡᴀʀᴅᴇᴅ ғʀᴏᴍ @BotFather 😑</b>')
    user_id = message.from_user.id
    msg = await message.reply_text("**👨‍💻 ᴡᴀɪᴛ ᴀ ᴍɪɴᴜᴛᴇ ɪ ᴀᴍ ᴄʀᴇᴀᴛɪɴɢ ʏᴏᴜʀ ʙᴏᴛ ❣️**")
    try:
        vj = Client(
            f"{bot_token}", API_ID, API_HASH,
            bot_token=bot_token,
            plugins={"root": "clone_plugins"}
        )
        await vj.start()
        bot = await vj.get_me()
        details = {
            'bot_id': bot.id,
            'is_bot': True,
            'user_id': user_id,
            'name': bot.first_name,
            'token': bot_token,
            'username': bot.username
        }
        mongo_db.bots.update_one({'bot_id': bot.id}, {'$set': details}, upsert=True)
        await set_clone_menu(vj, user_id)
        await msg.edit_text(f"<b>sᴜᴄᴄᴇssғᴜʟʟʏ ᴄʟᴏɴᴇᴅ ʏᴏᴜʀ ʙᴏᴛ: @{bot.username}.</b>")
    except BaseException as e:
        await msg.edit_text(f"⚠️ <b>Bot Error:</b>\n\n<code>{e}</code>\n\n**Kindly check the Render logs for the exact error.**")


@Client.on_message(filters.command("deletecloned") & filters.private)
async def delete_cloned_bot(client, message):
    if CLONE_MODE == False:
        return
    try:
        techvj = await client.ask(message.chat.id, "**Send Me Bot Token To Delete**")
        bot_token = re.findall(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', techvj.text, re.IGNORECASE)
        bot_token = bot_token[0] if bot_token else None
        cloned_bot = mongo_db.bots.find_one({"token": bot_token})
        if cloned_bot:
            mongo_db.bots.delete_one({"token": bot_token})
            await message.reply_text("**🤖 ᴛʜᴇ ᴄʟᴏɴᴇᴅ ʙᴏᴛ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴛʜᴇ ʟɪsᴛ ᴀɴᴅ ɪᴛs ᴅᴇᴛᴀɪʟs ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ. ☠️**")
        else:
            await message.reply_text("**⚠️ ᴛʜᴇ ʙᴏᴛ ᴛᴏᴋᴇɴ ᴘʀᴏᴠɪᴅᴇᴅ ɪs ɴᴏᴛ ɪɴ ᴛʜᴇ ᴄʟᴏɴᴇᴅ ʟɪsᴛ.**")
    except Exception:
        await message.reply_text("An error occurred while deleting the cloned bot.")


async def restart_bots():
    bots = list(mongo_db.bots.find())
    for bot in bots:
        bot_token = bot['token']
        try:
            vj = Client(
                f"{bot_token}", API_ID, API_HASH,
                bot_token=bot_token,
                plugins={"root": "clone_plugins"},
            )
            await vj.start()
            await set_clone_menu(vj, bot.get('user_id'))
        except Exception:
            pass
