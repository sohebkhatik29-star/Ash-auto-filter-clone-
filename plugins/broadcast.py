# Don't Remove Credit Tg - @movies_1780
# Subscribe YouTube Channel For Amazing Bot https://www.youtube.com/@tech_as_0
# Ask Doubt on telegram @movies_1780

from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS, BOT_USERNAME
import asyncio
MASTER_BROADCAST_CACHE = []
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

async def unpin_chat_message_both_sides(bot, chat_id, message_id):
    try:
        from pyrogram.raw.functions.messages import UpdatePinnedMessage
        peer = await bot.resolve_peer(chat_id)
        await bot.invoke(UpdatePinnedMessage(peer=peer, id=message_id, silent=False, unpin=True, pm_oneside=False))
        return True
    except (TypeError, Exception):
        pass
    try:
        await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
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
        return True, "Success", m.id
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(bot, user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted", None
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked", None
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error", None
    except Exception as e:
        return False, "Error", None

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

    user_pins = {}
    owner_copy_id = None
    async for user in users:
        if 'id' in user:
            pti, sh, mid = await broadcast_messages(bot, int(user['id']), b_msg)
            if pti:
                success += 1
                if mid:
                    user_pins[str(user['id'])] = mid
                    if int(user['id']) == int(message.chat.id):
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

    try:
        source_id = int(getattr(b_msg, 'id', None) or getattr(b_msg, 'message_id', None) or 0)
        raw_text = getattr(b_msg, 'text', None) or getattr(b_msg, 'caption', None) or ''
        text_content = str(raw_text).strip() if raw_text else ''
        
        clean_user_pins = {}
        pins_list = []
        all_ids = []
        if source_id:
            all_ids.append(int(source_id))
        if owner_copy_id:
            all_ids.append(int(owner_copy_id))
            
        for u_k, u_v in user_pins.items():
            try:
                u_int = int(u_k)
                m_int = int(u_v)
                clean_user_pins[str(u_int)] = m_int
                pins_list.append({"uid": u_int, "mid": m_int})
                all_ids.append(m_int)
            except Exception:
                pass
                
        all_ids = list(set(all_ids))

        record_doc = {
            "source_chat_id": int(message.chat.id),
            "source_msg_id": source_id if source_id else None,
            "owner_copy_id": int(owner_copy_id) if owner_copy_id else None,
            "text": text_content,
            "all_msg_ids": all_ids,
            "user_messages": clean_user_pins,
            "user_pins_list": pins_list,
            "created_at": float(time.time()),
            "status": "pinned"
        }

        MASTER_BROADCAST_CACHE.append(dict(record_doc))
        if len(MASTER_BROADCAST_CACHE) > 50:
            MASTER_BROADCAST_CACHE.pop(0)

        await db.col.database["master_broadcast_pins"].insert_one(dict(record_doc))
    except Exception as e:
        print(f"Error saving master broadcast record: {e}")
        
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"📢 <b>Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Users: {total_users}\n✅ Success (📌 Pinned): {success}\n🚫 Blocked: {blocked}\n🗑️ Deleted: {deleted}")

@Client.on_message(filters.command(["an_broadcast", "un_broadcast", "anbroadcast", "unbroadcast"]) & filters.user(ADMINS))
async def an_broadcast_cmd(bot, message):
    me = bot.me or (await bot.get_me())
    if me and me.username and BOT_USERNAME and me.username.lower() != BOT_USERNAME.lower():
        return
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text(
            "⚠️ <b>Please reply to the message you want to unpin!</b>\n\n"
            "<i>Jis broadcast message ko aap unpin karna chahte hain, us message ke reply me <code>/an_broadcast</code> command bhejein.</i>"
        )

    reply_id = int(reply.id)
    raw_reply_text = getattr(reply, 'text', None) or getattr(reply, 'caption', None) or ''
    reply_text = str(raw_reply_text).strip() if raw_reply_text else ''

    record = None

    # 1. Check in-memory cache
    for rec in reversed(MASTER_BROADCAST_CACHE):
        if reply_id in rec.get("all_msg_ids", []):
            record = rec
            break
        if rec.get("source_msg_id") == reply_id or rec.get("owner_copy_id") == reply_id:
            record = rec
            break
        if rec.get("user_messages", {}).get(str(message.chat.id)) == reply_id:
            record = rec
            break
        if reply_text and rec.get("text") and (reply_text == rec.get("text") or reply_text in rec.get("text") or rec.get("text") in reply_text):
            record = rec
            break

    # 2. Check Database
    col = db.col.database["master_broadcast_pins"]
    if not record:
        query_filter = {
            "$or": [
                {"all_msg_ids": reply_id},
                {"source_msg_id": reply_id},
                {"owner_copy_id": reply_id},
                {"user_pins_list.mid": reply_id},
                {f"user_messages.{message.chat.id}": reply_id}
            ]
        }
        try:
            record = await col.find_one(query_filter, sort=[("created_at", -1)])
        except Exception:
            pass

    if not record and reply_text:
        try:
            record = await col.find_one({"text": reply_text}, sort=[("created_at", -1)])
        except Exception:
            pass
            
    if not record and reply_text and len(reply_text) >= 5:
        try:
            import re
            prefix = re.escape(reply_text[:40])
            record = await col.find_one({"text": {"$regex": f"^{prefix}", "$options": "i"}}, sort=[("created_at", -1)])
        except Exception:
            pass

    if not record:
        try:
            latest = await col.find_one({}, sort=[("created_at", -1)])
            if latest:
                latest_text = latest.get("text", "")
                if (reply_text and latest_text and (reply_text in latest_text or latest_text in reply_text)) or (time.time() - latest.get("created_at", 0) < 7200):
                    record = latest
        except Exception:
            pass

    if not record and MASTER_BROADCAST_CACHE:
        record = MASTER_BROADCAST_CACHE[-1]

    if not record:
        try:
            await unpin_chat_message_both_sides(bot, message.chat.id, reply_id)
        except Exception:
            pass
        return await message.reply_text(
            "⚠️ <b>Broadcast record not found in database!</b>\n\n"
            "<i>Yeh message aapke chat se unpin kar diya gaya hai. Aage se jab aap broadcast karenge, toh /an_broadcast ka use karke aap har user ke chat se specific message unpin kar sakte hain.</i>"
        )

    user_messages = record.get("user_messages", {})
    if not user_messages and record.get("user_pins_list"):
        user_messages = {str(item["uid"]): item["mid"] for item in record["user_pins_list"]}
        
    total_users = len(user_messages)

    sts = await message.reply_text(text='⏳ <b>Unpinning this broadcast message from all users...</b>')
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
    if record.get("source_msg_id") and record.get("source_msg_id") != reply_id:
        try:
            await unpin_chat_message_both_sides(bot, message.chat.id, record["source_msg_id"])
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

    if record in MASTER_BROADCAST_CACHE:
        try:
            MASTER_BROADCAST_CACHE.remove(record)
        except Exception:
            pass
    try:
        if "_id" in record:
            await col.delete_one({"_id": record["_id"]})
    except Exception:
        pass

    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.edit(f"✅ <b>Unpin Broadcast Completed:</b>\nCompleted in {time_taken} seconds.\n\n👥 Total Target: {total_users}\n📌 Unpinned from: {unpinned} users\n❌ Failed/Inactive: {failed}")
