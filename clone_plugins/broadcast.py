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
        user_pins = {}
        owner_copy_id = None
        async for user in users:
            if "user_id" in user:
                uid = int(user["user_id"])
                pti, sh, mid = await broadcast_messages(bot, me.id, uid, b_msg)
                if pti:
                    success += 1
                    if mid:
                        user_pins[str(uid)] = mid
                        if uid == int(message.chat.id):
                            owner_copy_id = mid
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
        try:
            source_id = getattr(b_msg, "id", None) or getattr(b_msg, "message_id", None)
            text_content = (getattr(b_msg, "text", "") or getattr(b_msg, "caption", "") or "").strip()
            await clonedb.db[f"broadcast_pins_{me.id}"].insert_one({
                "bot_id": me.id,
                "source_chat_id": message.chat.id,
                "source_msg_id": source_id,
                "owner_copy_id": owner_copy_id,
                "text": text_content,
                "created_at": time.time(),
                "user_messages": user_pins
            })
        except Exception as e:
            print(f"Error saving clone broadcast record: {e}")
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
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text(
            "⚠️ <b>Please reply to the message you want to unpin!</b>\n\n"
            "<i>Jis broadcast message ko aap unpin karna chahte hain, us message ke reply me <code>/an_broadcast</code> command bhejein.</i>"
        )
    me = await bot.get_me()
    reply_id = reply.id
    reply_text = (getattr(reply, 'text', '') or getattr(reply, 'caption', '') or '').strip()

    col = clonedb.db[f"broadcast_pins_{me.id}"]
    query_filter = {
        "$or": [
            {"source_msg_id": reply_id},
            {"owner_copy_id": reply_id},
            {f"user_messages.{message.chat.id}": reply_id}
        ]
    }
    record = await col.find_one(query_filter, sort=[("created_at", -1)])
    if not record and reply_text:
        record = await col.find_one({"text": reply_text}, sort=[("created_at", -1)])

    if not record:
        return await message.reply_text(
            "❌ <b>No broadcast record found for this message!</b>\n\n"
            "<i>Kripya usi message ka reply dein jo is bot se broadcast kiya gaya ho.</i>"
        )

    user_messages = record.get("user_messages", {})
    total_users = len(user_messages)

    sts = await message.reply_text('⏳ <b>Unpinning this broadcast message from all users...</b>')
    start_time = time.time()
    done = 0
    unpinned = 0
    failed = 0

    try:
        await unpin_chat_message_both_sides(bot, message.chat.id, reply_id)
    except Exception:
        pass
    if record.get("owner_copy_id") and record.get("owner_copy_id") != reply_id:
        try:
            await unpin_chat_message_both_sides(bot, message.chat.id, record["owner_copy_id"])
        except Exception:
            pass

    for uid_str, msg_id in user_messages.items():
        uid = int(uid_str)
        if uid == int(message.chat.id):
            unpinned += 1
            done += 1
            continue
        try:
            if await unpin_chat_message_both_sides(bot, uid, msg_id):
                unpinned += 1
            else:
                failed += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                if await unpin_chat_message_both_sides(bot, uid, msg_id):
                    unpinned += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        done += 1
        if not done % 20:
            try:
                await sts.edit(f"⏳ <b>Unpinning in progress:</b>\n\n👥 Total Target: {total_users}\n🔄 Completed: {done} / {total_users}\n📌 Unpinned: {unpinned}\n❌ Failed/Inactive: {failed}")
            except Exception:
                pass
        await asyncio.sleep(0.04)

    try:
        await col.delete_one({"_id": record["_id"]})
    except Exception:
        pass

    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"✅ <b>Unpin Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Target: {total_users}\n📌 Unpinned from: {unpinned} users\n❌ Failed/Inactive: {failed}")
