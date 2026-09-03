# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS, BOT_USERNAME
import asyncio
import datetime
import time

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

async def pin_chat_message_both_sides(bot, chat_id, message_id):
    try:
        await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=False, both_sides=True)
        return True
    except (TypeError, Exception):
        pass
    try:
        from pyrogram.raw.functions.messages import UpdatePinnedMessage
        peer = await bot.resolve_peer(chat_id)
        await bot.invoke(UpdatePinnedMessage(peer=peer, id=message_id, silent=False, unpin=False, pm_oneside=False))
        return True
    except Exception:
        pass
    try:
        await bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=False)
        return True
    except Exception:
        pass
    return False

async def unpin_all_both_sides(bot, chat_id):
    try:
        await bot.unpin_all_chat_messages(chat_id=chat_id)
        return True
    except Exception:
        pass
    try:
        from pyrogram.raw.functions.messages import UnpinAllMessages
        peer = await bot.resolve_peer(chat_id)
        await bot.invoke(UnpinAllMessages(peer=peer))
        return True
    except Exception:
        pass
    return False

async def broadcast_messages(bot, user_id, message):
    try:
        m = await message.copy(chat_id=user_id)
        await pin_chat_message_both_sides(bot, user_id, m.id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(bot, user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception as e:
        return False, "Error"

# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def verupikkals(bot, message):
    me = bot.me or (await bot.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    
    b_msg = message.reply_to_message
    if not b_msg:
        if len(message.command) > 1:
            raw_text = message.text.split(None, 1)[1]
            b_msg = await bot.send_message(message.chat.id, raw_text)
        else:
            try:
                await bot.send_message(chat_id=message.from_user.id, text="📝 <b>Now Send Me Your Broadcast Message</b>\n\n(Send /cancel to abort)")
                if hasattr(bot, "listen"):
                    b_msg = await bot.listen(chat_id=message.from_user.id, timeout=300)
                else:
                    b_msg = await bot.ask(chat_id=message.from_user.id, text="", timeout=300)
                if not b_msg or getattr(b_msg, "text", "") == "/cancel":
                    return await message.reply("❌ Broadcast cancelled.")
            except Exception:
                return await message.reply("❌ Broadcast cancelled or timed out.")

    users = await db.get_all_users()
    sts = await message.reply_text(text='⏳ <b>Broadcasting your messages...</b>')
    start_time = time.time()
    total_users = await db.total_users_count()
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

    async for user in users:
        if 'id' in user:
            pti, sh = await broadcast_messages(bot, int(user['id']), b_msg)
            if pti:
                success += 1
            elif pti == False:
                if sh == "Blocked":
                    blocked += 1
                elif sh == "Deleted":
                    deleted += 1
                elif sh == "Error":
                    failed += 1
            done += 1
            if not done % 20:
                try:
                    await sts.edit(f"⏳ <b>Broadcast in progress:</b>\n\n👥 Total Users: {total_users}\n🔄 Completed: {done} / {total_users}\n✅ Success: {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")
                except Exception:
                    pass
        else:
            done += 1
            failed += 1
            if not done % 20:
                try:
                    await sts.edit(f"⏳ <b>Broadcast in progress:</b>\n\n👥 Total Users: {total_users}\n🔄 Completed: {done} / {total_users}\n✅ Success: {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")
                except Exception:
                    pass
        await asyncio.sleep(0.04)
        
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"📢 <b>Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Users: {total_users}\n✅ Success (📌 Pinned): {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")

@Client.on_message(filters.command(["an_broadcast", "un_broadcast", "anbroadcast", "unbroadcast"]) & filters.user(ADMINS))
async def an_broadcast_cmd(bot, message):
    me = bot.me or (await bot.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    
    users = await db.get_all_users()
    sts = await message.reply_text(text='⏳ <b>Unpinning broadcast message from all users...</b>')
    start_time = time.time()
    total_users = await db.total_users_count()
    done = 0
    unpinned = 0
    failed = 0
    
    async for user in users:
        if 'id' in user:
            try:
                if await unpin_all_both_sides(bot, int(user['id'])):
                    unpinned += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            done += 1
            if not done % 20:
                try:
                    await sts.edit(f"⏳ <b>Unpinning in progress:</b>\n\n👥 Total Users: {total_users}\n🔄 Completed: {done} / {total_users}\n📌 Unpinned: {unpinned}\n❌ Failed/Inactive: {failed}")
                except Exception:
                    pass
            await asyncio.sleep(0.04)
            
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"✅ <b>Unpin Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Users: {total_users}\n📌 Unpinned from: {unpinned} users\n❌ Failed/Inactive: {failed}")
