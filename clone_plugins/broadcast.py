# Don't Remove Credit @movies_1780
# Subscribe YouTube Channel For Amazing Bot @tech_as_0
# Ask Doubt on telegram @movies_1780
# Clone Code Credit : YT - @tech_as_0 / TG - @movies_1780 / GitHub - @VJBots

import datetime, time, asyncio
from pyrogram import Client, filters
from plugins.clone import mongo_db
from pyrogram.errors import *
from clone_plugins.dbusers import clonedb

async def pin_chat_message_both_sides(client, chat_id, message_id):
    try:
        await client.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=False, both_sides=True)
        return True
    except (TypeError, Exception):
        pass
    try:
        from pyrogram.raw.functions.messages import UpdatePinnedMessage
        peer = await client.resolve_peer(chat_id)
        await client.invoke(UpdatePinnedMessage(peer=peer, id=message_id, silent=False, unpin=False, pm_oneside=False))
        return True
    except Exception:
        pass
    try:
        await client.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=False)
        return True
    except Exception:
        pass
    return False

async def unpin_chat_message_both_sides(client, chat_id, message_id):
    try:
        await client.unpin_chat_message(chat_id=chat_id, message_id=message_id, both_sides=True)
        return True
    except (TypeError, Exception):
        pass
    try:
        from pyrogram.raw.functions.messages import UpdatePinnedMessage
        peer = await client.resolve_peer(chat_id)
        await client.invoke(UpdatePinnedMessage(peer=peer, id=message_id, silent=False, unpin=True, pm_oneside=False))
        return True
    except (TypeError, Exception):
        pass
    try:
        await client.unpin_chat_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception:
        pass
    return False

async def broadcast_messages(bot, bot_id, user_id, message):
    try:
        m = await message.copy(chat_id=user_id)
        await pin_chat_message_both_sides(bot, user_id, m.id)
        return True, "Success", m.id
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(bot, bot_id, user_id, message)
    except InputUserDeactivated:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Deleted", None
    except UserIsBlocked:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Blocked", None
    except PeerIdInvalid:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error", None
    except Exception as e:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error", None

@Client.on_message(filters.command("broadcast"))
async def pm_broadcast(bot, message):
    from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
    if not (is_bot_owner(bot, message.from_user.id) or has_permission(bot, message.from_user.id, "broadcast")):
        await message.reply_text("ᴏɴʟʏ ᴏᴡɴᴇʀ / ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅ❗")
        return
    b_msg = message.reply_to_message
    if not b_msg:
        try:
            b_msg = await bot.ask(chat_id=message.from_user.id, text="📝 <b>Now Send Me Your Broadcast Message</b>\n\n(Send /cancel to abort)", timeout=300)
            if not b_msg.text and not b_msg.media:
                return await message.reply("Invalid message.")
            if getattr(b_msg, 'text', '') == "/cancel":
                return await message.reply("❌ Broadcast cancelled.")
        except Exception:
            return await message.reply("❌ Broadcast cancelled or timed out.")
    
    from clone_plugins.advanced import execute_broadcast
    return await execute_broadcast(bot, message.chat.id, b_msg)

@Client.on_message(filters.command(["an_broadcast", "un_broadcast", "anbroadcast", "unbroadcast"]))
async def pm_an_broadcast(bot, message):
    from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
    if not (is_bot_owner(bot, message.from_user.id) or has_permission(bot, message.from_user.id, "broadcast")):
        await message.reply_text("ᴏɴʟʏ ᴏᴡɴᴇʀ / ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅ❗")
        return
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text(
            "⚠️ <b>Please reply to the message you want to unpin!</b>\n\n"
            "<i>Jis broadcast message ko aap unpin karna chahte hain, us message ke reply me <code>/an_broadcast</code> command bhejein.</i>"
        )
    from clone_plugins.advanced import execute_unpin_single_broadcast
    return await execute_unpin_single_broadcast(bot, message.chat.id, reply)
