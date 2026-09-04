import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import InputUserDeactivated, UserIsBlocked, FloodWait
from clone_plugins.dbusers import clonedb
from plugins.clone import mongo_db
from clone_plugins.users_api import parse_auto_delete_time, format_auto_delete_time
from config import ADMINS

def bot_record(client):
    if mongo_db is None:return {}
    try:return mongo_db.bots.find_one({"bot_id":client.me.id}) or {}
    except Exception:return {}
def owner_only(client,uid):
    d=bot_record(client)
    if int(d.get("user_id",0))==int(uid):return True
    try:return int(uid) in {int(x) for x in ADMINS}
    except:return False
def save(client,data):
    if mongo_db is not None:mongo_db.bots.update_one({"bot_id":client.me.id},{"$set":data},upsert=True)
def back_button(target="my_clone"):return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data=target)]])
def clone_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("START MSG",callback_data="clone_startmsg"),InlineKeyboardButton("FORCE SUB",callback_data="clone_force")],[InlineKeyboardButton("MODERATORS",callback_data="clone_mods"),InlineKeyboardButton("AUTO DELETE",callback_data="clone_autodelete")],[InlineKeyboardButton("NO FORWARD",callback_data="clone_noforward"),InlineKeyboardButton("ACCESS TOKEN",callback_data="clone_access")],[InlineKeyboardButton("TRANSFER DB",callback_data="clone_transfer"),InlineKeyboardButton("DEACTIVATE",callback_data="clone_deactivate")],[InlineKeyboardButton("MODE",callback_data="clone_mode"),InlineKeyboardButton("RESTART",callback_data="clone_restart")],[InlineKeyboardButton("STATS",callback_data="clone_stats"),InlineKeyboardButton("DELETE",callback_data="clone_delete")],[InlineKeyboardButton("‹ BACK",callback_data="my_clones")]])
async def settings(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    await message.reply("⚙️ <b>Settings</b>\n\nCustomize your settings as your need.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 MY CLONE BOT 🤖",callback_data="my_clones")],[InlineKeyboardButton("☁️ GOOGLE BACKUP",callback_data="google_backup")],[InlineKeyboardButton("🔗 LINK SHORTENER",callback_data="link_shortener")],[InlineKeyboardButton("✏️ CUSTOM CAPTION",callback_data="custom_caption")],[InlineKeyboardButton("🟢 CUSTOM BUTTON",callback_data="custom_button")],[InlineKeyboardButton("🛡️ PROTECT CONTENT",callback_data="protect_menu")],[InlineKeyboardButton("‹ BACK",callback_data="settings_back")]]))
async def force_sub(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if len(message.command)<2:return await message.reply("Usage: /force_sub @channel or /force_sub off")
    if message.command[1].lower()=="off":save(client,{"force_channels":[]});return await message.reply("✅ Force Subscribe disabled.")
    try:
        chat=await client.get_chat(message.command[1]);channels=list(bot_record(client).get("force_channels",[]));
        if chat.id not in channels:channels.append(chat.id)
        save(client,{"force_channels":channels});await message.reply("✅ Force Subscribe added. Make the bot admin in that channel.")
    except Exception:await message.reply("❌ Cannot access that channel. Make the bot admin first.")
async def caption(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    raw=message.text.split(None,1)[1] if len(message.command)>1 else "off"
    if raw.lower()=="off":save(client,{"custom_caption":None});return await message.reply("✅ Custom caption disabled.")
    save(client,{"custom_caption":raw});await message.reply("✅ Custom caption saved.")
async def button(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if len(message.command)<2 or message.command[1].lower()=="off":save(client,{"custom_buttons":[]});return await message.reply("✅ Custom buttons cleared.")
    raw=message.text.split(None,1)[1]
    if " - " not in raw:return await message.reply("Usage: /button Text - https://example.com")
    text,url=[x.strip() for x in raw.split(" - ",1)]
    if not url.startswith(("https://","http://")):return await message.reply("❌ Button URL must start with http:// or https://")
    buttons=list(bot_record(client).get("custom_buttons",[]));buttons.append({"text":text[:64],"url":url});save(client,{"custom_buttons":buttons});await message.reply("✅ Custom button added.")
async def protect(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    value=len(message.command)>1 and message.command[1].lower() in ("on","1","yes","true");save(client,{"protect_content":value});await message.reply(f"🛡️ Protect Content: <b>{'ON' if value else 'OFF'}</b>")
async def admin_panel(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    await message.reply("👑 <b>Owner Panel</b>",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings",callback_data="settings")],[InlineKeyboardButton("📊 Stats",callback_data="clone_stats"),InlineKeyboardButton("📢 Broadcast",callback_data="admin_broadcast")]]))
async def stats(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    await message.reply(f"📊 <b>Users:</b> <code>{await clonedb.total_users_count(client.me.id)}</code>")
def is_owner_or_admin(client, uid):
    try:
        from clone_plugins.clone_settings_ui import is_bot_owner, has_permission
        if is_bot_owner(client, uid) or has_permission(client, uid, "broadcast"):
            return True
    except Exception:
        pass
    return owner_only(client, uid)

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

async def unpin_all_both_sides(client, chat_id):
    try:
        await client.unpin_all_chat_messages(chat_id=chat_id)
        return True
    except Exception:
        pass
    try:
        from pyrogram.raw.functions.messages import UnpinAllMessages
        peer = await client.resolve_peer(chat_id)
        await client.invoke(UnpinAllMessages(peer=peer))
        return True
    except Exception:
        pass
    return False

BROADCAST_CACHE = {}

async def execute_broadcast(client, chat_id, b_msg):
    sts = await client.send_message(chat_id, "⏳ <b>Broadcasting your message...</b>")
    sent = 0
    failed = 0
    pinned = 0
    total_users = await clonedb.total_users_count(client.me.id)
    user_pins = {}
    owner_copy_id = None
    
    users = await clonedb.get_all_users(client.me.id)
    async for u in users:
        uid = u.get("user_id")
        if not uid:
            continue
        try:
            m = await b_msg.copy(uid)
            if await pin_chat_message_both_sides(client, uid, m.id):
                pinned += 1
            user_pins[str(uid)] = int(m.id)
            if int(uid) == int(chat_id):
                owner_copy_id = int(m.id)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                m = await b_msg.copy(uid)
                if await pin_chat_message_both_sides(client, uid, m.id):
                    pinned += 1
                user_pins[str(uid)] = int(m.id)
                if int(uid) == int(chat_id):
                    owner_copy_id = int(m.id)
                sent += 1
            except Exception:
                failed += 1
        except (InputUserDeactivated, UserIsBlocked):
            try:
                await clonedb.delete_user(client.me.id, uid)
            except Exception:
                pass
            failed += 1
        except Exception:
            failed += 1
            
        if (sent + failed) % 20 == 0:
            try:
                await sts.edit(
                    f"⏳ <b>Broadcast in progress:</b>\n\n"
                    f"👥 Total Users: {total_users}\n"
                    f"🔄 Completed: {sent + failed} / {total_users}\n"
                    f"✅ Sent: {sent} (📌 Pinned: {pinned})\n"
                    f"❌ Failed: {failed}"
                )
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
        bot_id = int(client.me.id)

        record_doc = {
            "bot_id": bot_id,
            "source_chat_id": int(chat_id),
            "source_msg_id": source_id if source_id else None,
            "owner_copy_id": int(owner_copy_id) if owner_copy_id else None,
            "text": text_content,
            "all_msg_ids": all_ids,
            "user_messages": clean_user_pins,
            "user_pins_list": pins_list,
            "created_at": float(time.time()),
            "status": "pinned"
        }

        # 1. In-memory cache
        BROADCAST_CACHE.setdefault(bot_id, []).append(dict(record_doc))
        if len(BROADCAST_CACHE[bot_id]) > 50:
            BROADCAST_CACHE[bot_id].pop(0)

        # 2. Async MongoDB (clonedb)
        try:
            await clonedb.db[f"broadcast_pins_{bot_id}"].insert_one(dict(record_doc))
        except Exception as e:
            print(f"Error saving to clonedb broadcast_pins: {e}")

        # 3. Synchronous mongo_db if available
        try:
            from plugins.clone import mongo_db
            if mongo_db is not None:
                mongo_db[f"broadcast_pins_{bot_id}"].insert_one(dict(record_doc))
        except Exception:
            pass
    except Exception as e:
        print(f"Error creating broadcast pin doc: {e}")
            
    return await sts.edit(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Sent & Pinned: {sent}\n"
        f"❌ Failed/Blocked: {failed}"
    )

async def execute_unpin_single_broadcast(client, chat_id, reply_msg):
    reply_id = int(reply_msg.id)
    raw_reply_text = getattr(reply_msg, 'text', None) or getattr(reply_msg, 'caption', None) or ''
    reply_text = str(raw_reply_text).strip() if raw_reply_text else ''
    bot_id = int(client.me.id)

    record = None
    
    # 1. In-memory cache search
    cached_list = BROADCAST_CACHE.get(bot_id, [])
    for rec in reversed(cached_list):
        if reply_id in rec.get("all_msg_ids", []):
            record = rec
            break
        if rec.get("source_msg_id") == reply_id or rec.get("owner_copy_id") == reply_id:
            record = rec
            break
        if rec.get("user_messages", {}).get(str(chat_id)) == reply_id:
            record = rec
            break
        if reply_text and rec.get("text") and (reply_text == rec.get("text") or reply_text in rec.get("text") or rec.get("text") in reply_text):
            record = rec
            break

    # 2. Async MongoDB (clonedb)
    col = clonedb.db[f"broadcast_pins_{bot_id}"]
    if not record:
        query_filter = {
            "$or": [
                {"all_msg_ids": reply_id},
                {"source_msg_id": reply_id},
                {"owner_copy_id": reply_id},
                {"user_pins_list.mid": reply_id},
                {f"user_messages.{chat_id}": reply_id}
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

    # 3. Synchronous mongo_db
    if not record:
        try:
            from plugins.clone import mongo_db
            if mongo_db is not None:
                record = mongo_db[f"broadcast_pins_{bot_id}"].find_one(query_filter, sort=[("created_at", -1)])
                if not record and reply_text:
                    record = mongo_db[f"broadcast_pins_{bot_id}"].find_one({"text": reply_text}, sort=[("created_at", -1)])
        except Exception:
            pass

    # 4. Check if there is any recent broadcast in DB
    if not record:
        try:
            latest = await col.find_one({}, sort=[("created_at", -1)])
            if latest:
                latest_text = latest.get("text", "")
                if (reply_text and latest_text and (reply_text in latest_text or latest_text in reply_text)) or (time.time() - latest.get("created_at", 0) < 7200):
                    record = latest
        except Exception:
            pass

    # 5. Fallback to latest in cache
    if not record and cached_list:
        record = cached_list[-1]

    # If still not found at all
    if not record:
        try:
            await unpin_chat_message_both_sides(client, chat_id, reply_id)
        except Exception:
            pass
        return await client.send_message(
            chat_id,
            "⚠️ <b>Broadcast record not found in database!</b>\n\n"
            "<i>Yeh message aapke chat se unpin kar diya gaya hai. Aage se jab aap broadcast karenge, toh /an_broadcast ka use karke aap har user ke chat se specific message unpin kar sakte hain.</i>"
        )

    user_messages = record.get("user_messages", {})
    if not user_messages and record.get("user_pins_list"):
        user_messages = {str(item["uid"]): item["mid"] for item in record["user_pins_list"]}
        
    total_users = len(user_messages)

    sts = await client.send_message(chat_id, "⏳ <b>Unpinning this broadcast message from all users...</b>")
    unpinned = 0
    failed = 0

    try:
        await unpin_chat_message_both_sides(client, chat_id, reply_id)
    except Exception:
        pass
    if record.get("owner_copy_id") and record.get("owner_copy_id") != reply_id:
        try:
            await unpin_chat_message_both_sides(client, chat_id, record["owner_copy_id"])
        except Exception:
            pass
    if record.get("source_msg_id") and record.get("source_msg_id") != reply_id:
        try:
            await unpin_chat_message_both_sides(client, chat_id, record["source_msg_id"])
        except Exception:
            pass

    for uid_str, msg_id in user_messages.items():
        uid = int(uid_str)
        if uid == int(chat_id):
            unpinned += 1
            continue
        try:
            if await unpin_chat_message_both_sides(client, uid, msg_id):
                unpinned += 1
            else:
                failed += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                if await unpin_chat_message_both_sides(client, uid, msg_id):
                    unpinned += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1

        if (unpinned + failed) % 20 == 0:
            try:
                await sts.edit(
                    f"⏳ <b>Unpinning in progress:</b>\n\n"
                    f"👥 Total Target: {total_users}\n"
                    f"🔄 Completed: {unpinned + failed} / {total_users}\n"
                    f"📌 Unpinned: {unpinned}\n"
                    f"❌ Inactive/Error: {failed}"
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    if record in cached_list:
        try:
            cached_list.remove(record)
        except Exception:
            pass
    try:
        if "_id" in record:
            await col.delete_one({"_id": record["_id"]})
    except Exception:
        pass
    try:
        from plugins.clone import mongo_db
        if mongo_db is not None and "_id" in record:
            mongo_db[f"broadcast_pins_{bot_id}"].delete_one({"_id": record["_id"]})
    except Exception:
        pass

    return await sts.edit(
        f"✅ <b>Unpin Complete!</b>\n\n"
        f"👥 Total Target: {total_users}\n"
        f"📌 Unpinned from: {unpinned} users\n"
        f"❌ Inactive/Failed: {failed}"
    )

async def broadcast(client, message):
    if not is_owner_or_admin(client, message.from_user.id):
        return await message.reply("❌ Owner or authorized admin only.")
    if message.reply_to_message:
        return await execute_broadcast(client, message.chat.id, message.reply_to_message)
    if len(message.command) > 1:
        raw_text = message.text.split(None, 1)[1]
        temp_msg = await client.send_message(message.chat.id, raw_text)
        return await execute_broadcast(client, message.chat.id, temp_msg)
    text = (
        "📢 <b>BROADCAST PANEL:</b>\n\n"
        "❝ <b>SEND A BROADCAST MESSAGE TO ALL USERS OF YOUR BOT. THE MESSAGE WILL BE AUTOMATICALLY PINNED IN THEIR CHAT SO EVERY USER WHO HAS STARTED THE BOT WILL SEE IT.</b> ❞"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 SEND BROADCAST", callback_data="bc_send_msg")],
        [InlineKeyboardButton("‹ BACK", callback_data="admin_panel_back")]
    ])
    await message.reply(text, reply_markup=markup)

async def an_broadcast(client, message):
    if not is_owner_or_admin(client, message.from_user.id):
        return await message.reply("❌ Owner or authorized admin only.")
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text(
            "⚠️ <b>Please reply to the message you want to unpin!</b>\n\n"
            "<i>Jis broadcast message ko aap unpin karna chahte hain, us message ke reply me <code>/an_broadcast</code> command bhejein.</i>"
        )
    return await execute_unpin_single_broadcast(client, message.chat.id, reply)

async def ban(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if len(message.command)!=2 or not message.command[1].isdigit():return await message.reply("Usage: /ban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id":int(message.command[1])},{"$set":{"banned":True}},upsert=True);await message.reply("🚫 User banned.")
async def unban(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if len(message.command)!=2 or not message.command[1].isdigit():return await message.reply("Usage: /unban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id":int(message.command[1])},{"$set":{"banned":False}},upsert=True);await message.reply("✅ User unbanned.")
async def auto_delete(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    args=message.command[1:]
    if not args:
        d=bot_record(client)
        ad_sec = int(d.get("auto_delete_time") or (int(d.get("auto_delete_minutes",15))*60))
        t_str = format_auto_delete_time(ad_sec)
        return await message.reply(f"🗑️ Auto Delete: {'ON' if d.get('auto_delete_enabled') else 'OFF'}\nTime: {t_str}")
    if args[0].lower()=="off":
        save(client,{"auto_delete_enabled":False});return await message.reply("🗑️ Auto Delete disabled.")
    time_arg = "15m"
    if len(args)>1:
        time_arg = args[1]
    elif len(args)==1 and args[0].lower() not in ("on", "true", "1"):
        time_arg = args[0]
    sec = parse_auto_delete_time(time_arg)
    mins = max(1, sec // 60)
    save(client,{"auto_delete_enabled":True,"auto_delete_time":sec,"auto_delete_minutes":mins})
    t_str = format_auto_delete_time(sec)
    await message.reply(f"🗑️ Auto Delete enabled for {t_str}.")
async def no_forward(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    d=bot_record(client);value=bool(d.get("no_forward",False)) if len(message.command)==1 else message.command[1].lower() in ("on","1","yes","true");save(client,{"no_forward":value});await message.reply(f"🚫 No Forward: <b>{'Enabled ✅' if value else 'Disabled ❌'}</b>")
async def moderators(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    mods=[int(x) for x in bot_record(client).get("moderators",[]) if str(x).isdigit()]
    if len(message.command)==1:return await message.reply("👮 <b>Moderators</b>\n\n"+("\n".join(f"• <code>{x}</code>" for x in mods) if mods else "No moderators.")+"\n\nUse /moderator add USER_ID or /moderator del USER_ID")
    if len(message.command)!=3 or not message.command[2].isdigit():return await message.reply("Usage: /moderator add USER_ID")
    uid=int(message.command[2])
    if message.command[1].lower()=="add" and uid not in mods:mods.append(uid)
    elif message.command[1].lower()=="del":mods=[x for x in mods if x!=uid]
    else:return await message.reply("Usage: /moderator add USER_ID or /moderator del USER_ID")
    save(client,{"moderators":mods});await message.reply("✅ Moderator list updated.")
async def access_token(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    d=bot_record(client)
    if len(message.command)==1:return await message.reply(f"🔑 Access Token: {'ON' if d.get('access_token_enabled',True) else 'OFF'}\nValidity: {d.get('access_token_hours',1)} hour(s)")
    if message.command[1].lower()=="off":save(client,{"access_token_enabled":False});return await message.reply("🔑 Access Token disabled.")
    hours=1
    if len(message.command)>2:
        try:hours=max(1,min(168,int(message.command[2])))
        except:return await message.reply("Usage: /access_token on 1")
    save(client,{"access_token_enabled":True,"access_token_hours":hours});await message.reply(f"🔑 Access Token enabled. Validity: {hours} hour(s).")
async def transfer_db(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if len(message.command)<2 or not message.command[1].isdigit():return await message.reply("Usage: /transfer_db OLD_BOT_ID")
    await message.reply("🔄 Transfer request received. Use the selected clone workflow from Master → My Clone Bot.")
async def deactivate(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    value=len(message.command)>1 and message.command[1].lower() in ("on","1","yes","true");save(client,{"deactivated":value});await message.reply("⏸ Clone deactivated." if value else "▶️ Clone activated.")
async def mode(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    current=message.command[1].lower() if len(message.command)>1 else bot_record(client).get("mode","private")
    if current not in ("private","public"):return await message.reply("Usage: /mode public or /mode private")
    save(client,{"mode":current});await message.reply(f"🔒 Clone Mode: {current.title()}")
async def restart(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    save(client,{"restart_requested":True});await message.reply("🔄 Settings saved. Restart the service to reload this clone.")
async def delete_clone(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    await message.reply("⚠️ Delete this clone record?",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("YES, DELETE",callback_data="delete_confirm"),InlineKeyboardButton("CANCEL",callback_data="my_clone")]]))
async def startmsg(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    if not message.reply_to_message:return await message.reply("Reply to a message/photo and use /start_msg")
    txt=message.reply_to_message.text or message.reply_to_message.caption or "";save(client,{"start_message":txt[:4000]});await message.reply("✅ Start message saved.")
async def clone_callback(client,query):
    if query.data=="my_clone":return await query.message.edit_text("🛠 <b>Customize Clone</b>",reply_markup=clone_menu())
    if query.data=="clone_stats":return await query.message.edit_text(f"📊 <b>Users:</b> <code>{await clonedb.total_users_count(client.me.id)}</code>",reply_markup=back_button())
    if query.data=="clone_delete":return await query.message.edit_text("⚠️ Delete this clone record?",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("YES, DELETE",callback_data="delete_confirm"),InlineKeyboardButton("CANCEL",callback_data="my_clone")]]))
    if query.data=="delete_confirm" and owner_only(client,query.from_user.id) and mongo_db is not None:mongo_db.bots.delete_one({"bot_id":client.me.id});return await query.message.edit_text("🗑️ <b>Clone record deleted.</b>")
    
    if query.data == "admin_broadcast":
        if not is_owner_or_admin(client, query.from_user.id):
            return await query.answer("❌ Owner only.", show_alert=True)
        await query.answer()
        text = (
            "📢 <b>BROADCAST PANEL:</b>\n\n"
            "❝ <b>SEND A BROADCAST MESSAGE TO ALL USERS OF YOUR BOT. THE MESSAGE WILL BE AUTOMATICALLY PINNED IN THEIR CHAT SO EVERY USER WHO HAS STARTED THE BOT WILL SEE IT.</b> ❞"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 SEND BROADCAST", callback_data="bc_send_msg")],
            [InlineKeyboardButton("‹ BACK", callback_data="admin_panel_back")]
        ])
        return await query.message.edit_text(text, reply_markup=markup)

    if query.data == "admin_panel_back":
        await query.answer()
        return await query.message.edit_text(
            "👑 <b>Owner Panel</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
                [InlineKeyboardButton("📊 Stats", callback_data="clone_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
            ])
        )

    if query.data == "bc_cancel":
        await query.answer("Cancelled.")
        try:
            query.stop_propagation()
        except Exception:
            pass
        try:
            from clone_plugins.sessions import cancel_all_listeners
            cancel_all_listeners(client, query.from_user.id)
        except Exception:
            pass
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if query.data == "bc_send_msg":
        if not is_owner_or_admin(client, query.from_user.id):
            return await query.answer("❌ Owner only", show_alert=True)
        await query.answer()
        try:
            query.stop_propagation()
        except Exception:
            pass
        try:
            await query.message.delete()
        except Exception:
            pass
        prompt_msg = await client.send_message(
            chat_id=query.from_user.id,
            text=(
                "📝 <b>Now send me your broadcast message:</b>\n\n"
                "<i>You can send text, photo, video, document, audio or forward any message.</i>\n\n"
                "(Send /cancel to abort)"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ CANCEL", callback_data="bc_cancel")]])
        )
        try:
            if hasattr(client, "listen"):
                b_msg = await client.listen(chat_id=query.from_user.id, timeout=300)
            elif hasattr(client, "ask"):
                b_msg = await client.ask(chat_id=query.from_user.id, text="", timeout=300)
            else:
                b_msg = await client.listen(chat_id=query.from_user.id, timeout=300)
            if not b_msg or getattr(b_msg, 'text', '') == "/cancel":
                try:
                    await prompt_msg.delete()
                except Exception:
                    pass
                return await client.send_message(query.from_user.id, "❌ Broadcast cancelled.")
        except Exception:
            try:
                await prompt_msg.delete()
            except Exception:
                pass
            return await client.send_message(query.from_user.id, "❌ Broadcast cancelled or timed out.")
        try:
            await prompt_msg.delete()
        except Exception:
            pass
        return await execute_broadcast(client, query.from_user.id, b_msg)

    if query.data == "bc_unpin_msg":
        await query.answer("⚠️ Reply to the broadcast message with /an_broadcast to unpin that specific message.", show_alert=True)
        try:
            query.stop_propagation()
        except Exception:
            pass
        return
    await query.answer("Use the command for this setting.",show_alert=True)
def register(client):
    private=filters.private
    for fn,cmd in [(settings,"settings"),(force_sub,"force_sub"),(caption,"caption"),(button,"button"),(protect,"protect"),(admin_panel,"admin"),(stats,"stats"),(broadcast,"broadcast"),(an_broadcast,"an_broadcast"),(an_broadcast,"un_broadcast"),(an_broadcast,"anbroadcast"),(an_broadcast,"unbroadcast"),(ban,"ban"),(unban,"unban"),(auto_delete,"auto_delete"),(no_forward,"no_forward"),(moderators,"moderator"),(access_token,"access_token"),(transfer_db,"transfer_db"),(deactivate,"deactivate"),(mode,"mode"),(restart,"restart"),(delete_clone,"delete"),(startmsg,"start_msg")]:client.add_handler(MessageHandler(fn,filters.command(cmd)&private),group=1)
    client.add_handler(CallbackQueryHandler(clone_callback,filters.regex(r"^(my_clone|clone_stats|clone_delete|delete_confirm|admin_broadcast|bc_send_msg|bc_unpin_msg|admin_panel_back|bc_cancel)$")),group=1);return client

callbacks = clone_callback
