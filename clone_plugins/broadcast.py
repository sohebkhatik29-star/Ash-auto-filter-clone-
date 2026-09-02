# Don't Remove Credit @movies_1780
# Subscribe YouTube Channel For Amazing Bot @tech_as_0
# Ask Doubt on telegram @movies_1780
# Clone Code Credit : YT - @tech_as_0 / TG - @movies_1780 / GitHub - @VJBots

import datetime, time, asyncio
from pyrogram import Client, filters
from plugins.clone import mongo_db
from pyrogram.errors import *
from clone_plugins.dbusers import clonedb

async def broadcast_messages(bot, bot_id, user_id, message):
    try:
        m = await message.copy(chat_id=user_id)
        try:
            await bot.pin_chat_message(chat_id=user_id, message_id=m.id, disable_notification=False)
        except Exception:
            pass
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(bot, bot_id, user_id, message)
    except InputUserDeactivated:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Deleted"
    except UserIsBlocked:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Blocked"
    except PeerIdInvalid:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error"
    except Exception as e:
        await clonedb.delete_user(bot_id, user_id)
        return False, "Error"

@Client.on_message(filters.command("broadcast"))
async def pm_broadcast(bot, message):
    from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
    if not (is_bot_owner(bot, message.from_user.id) or has_permission(bot, message.from_user.id, "broadcast")):
        await message.reply_text("ᴏɴʟʏ ᴏᴡɴᴇʀ / ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅ❗")
        return
    me = await bot.get_me()
    b_msg = message.reply_to_message
    if not b_msg:
        try:
            b_msg = await bot.ask(chat_id = message.from_user.id, text = "📝 <b>Now Send Me Your Broadcast Message</b>\n\n(Send /cancel to abort)", timeout=300)
            if not b_msg.text and not b_msg.media:
                return await message.reply("Invalid message.")
            if getattr(b_msg, 'text', '') == "/cancel":
                return await message.reply("❌ Broadcast cancelled.")
        except Exception:
            return await message.reply("❌ Broadcast cancelled or timed out.")
    try:
        users = await clonedb.get_all_users(me.id)
        sts = await message.reply_text('⏳ <b>Broadcasting your messages...</b>')
        start_time = time.time()
        total_users = await clonedb.total_users_count(me.id)
        done = 0
        blocked = 0
        deleted = 0
        failed = 0
        success = 0
        async for user in users:
            if 'user_id' in user:
                pti, sh = await broadcast_messages(bot, me.id, int(user['user_id']), b_msg)
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
                    await sts.edit(f"⏳ <b>Broadcast in progress:</b>\n\n👥 Total Users {total_users}\n🔄 Completed: {done} / {total_users}\n✅ Success: {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")
            else:
                done += 1
                failed += 1
                if not done % 20:
                    await sts.edit(f"⏳ <b>Broadcast in progress:</b>\n\n👥 Total Users {total_users}\n🔄 Completed: {done} / {total_users}\n✅ Success: {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")
            await asyncio.sleep(0.04)
        time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
        await sts.edit(f"📢 <b>Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Users: {total_users}\n✅ Success (📌 Pinned): {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")
    except Exception as e:
        print(f"error: {e}")

@Client.on_message(filters.command(["an_broadcast", "un_broadcast", "anbroadcast", "unbroadcast"]))
async def pm_an_broadcast(bot, message):
    from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
    if not (is_bot_owner(bot, message.from_user.id) or has_permission(bot, message.from_user.id, "broadcast")):
        await message.reply_text("ᴏɴʟʏ ᴏᴡɴᴇʀ / ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅ❗")
        return
    me = await bot.get_me()
    try:
        users = await clonedb.get_all_users(me.id)
        sts = await message.reply_text('⏳ <b>Unpinning broadcast message from all users...</b>')
        start_time = time.time()
        total_users = await clonedb.total_users_count(me.id)
        done = 0
        unpinned = 0
        failed = 0
        async for user in users:
            if 'user_id' in user:
                try:
                    await bot.unpin_all_chat_messages(chat_id=int(user['user_id']))
                    unpinned += 1
                except Exception:
                    failed += 1
                done += 1
                if not done % 20:
                    await sts.edit(f"⏳ <b>Unpinning in progress:</b>\n\n👥 Total Users: {total_users}\n🔄 Completed: {done} / {total_users}\n📌 Unpinned: {unpinned}\n❌ Failed/Inactive: {failed}")
                await asyncio.sleep(0.04)
        time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
        await sts.edit(f"✅ <b>Unpin Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Users: {total_users}\n📌 Unpinned from: {unpinned} users\n❌ Failed/Inactive: {failed}")
    except Exception as e:
        print(f"error: {e}")
