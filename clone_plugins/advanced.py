import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
async def broadcast(client,message):
    if not owner_only(client,message.from_user.id):return await message.reply("❌ Owner only.")
    text = (
        "📢 <b>BROADCAST PANEL:</b>\n\n"
        "❝ <b>SEND A BROADCAST MESSAGE TO ALL USERS OF YOUR BOT. THE MESSAGE WILL BE AUTOMATICALLY PINNED IN THEIR CHAT SO EVERY USER WHO HAS STARTED THE BOT WILL SEE IT.</b> ❞"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 SEND BROADCAST", callback_data="bc_send_msg")],
        [InlineKeyboardButton("‹ BACK", callback_data="admin_panel_back")]
    ])
    await message.reply(text, reply_markup=markup)
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
    
    if query.data=="admin_broadcast":
        if not owner_only(client,query.from_user.id):return await query.answer("❌ Owner only.", show_alert=True)
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
        return await query.message.edit_text("👑 <b>Owner Panel</b>",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings",callback_data="settings")],[InlineKeyboardButton("📊 Stats",callback_data="clone_stats"),InlineKeyboardButton("📢 Broadcast",callback_data="admin_broadcast")]]))

    if query.data == "bc_send_msg":
        if not owner_only(client, query.from_user.id):
            return await query.answer("❌ Owner only", show_alert=True)
        try:
            b_msg = await client.ask(chat_id=query.from_user.id, text="📝 <b>Now Send Me Your Broadcast Message</b>\n\n(Send /cancel to abort)", timeout=300)
            if not b_msg.text and not b_msg.media:
                return await query.message.reply("Invalid message.")
            if getattr(b_msg, 'text', '') == "/cancel":
                return await query.message.reply("❌ Broadcast cancelled.")
        except Exception as e:
            return await query.message.reply("❌ Broadcast cancelled or timed out.")

        sts = await query.message.reply("⏳ <b>Broadcasting your message...</b>")
        sent = failed = 0
        total_users = await clonedb.total_users_count(client.me.id)
        
        async for u in clonedb.get_all_users(client.me.id):
            try:
                m = await b_msg.copy(u["user_id"])
                try:
                    await client.pin_chat_message(chat_id=u["user_id"], message_id=m.id, disable_notification=False)
                except Exception:
                    pass
                sent += 1
            except Exception:
                failed += 1
            
            if (sent + failed) % 20 == 0:
                try:
                    await sts.edit(f"⏳ <b>Broadcast in progress:</b>\n\nCompleted: {sent+failed} / {total_users}\nSuccess: {sent}\nFailed: {failed}")
                except Exception:
                    pass
            await asyncio.sleep(.05)
            
        return await sts.edit(f"📢 <b>Broadcast Complete!</b>\n\nTotal Users: {total_users}\nSuccess: {sent}\nFailed: {failed}")

    await query.answer("Use the command for this setting.",show_alert=True)
def register(client):
    private=filters.private
    for fn,cmd in [(settings,"settings"),(force_sub,"force_sub"),(caption,"caption"),(button,"button"),(protect,"protect"),(admin_panel,"admin"),(stats,"stats"),(broadcast,"broadcast"),(ban,"ban"),(unban,"unban"),(auto_delete,"auto_delete"),(no_forward,"no_forward"),(moderators,"moderator"),(access_token,"access_token"),(transfer_db,"transfer_db"),(deactivate,"deactivate"),(mode,"mode"),(restart,"restart"),(delete_clone,"delete"),(startmsg,"start_msg")]:client.add_handler(MessageHandler(fn,filters.command(cmd)&private),group=1)
    client.add_handler(CallbackQueryHandler(clone_callback,filters.regex(r"^(my_clone|clone_stats|clone_delete|delete_confirm|admin_broadcast|bc_send_msg|admin_panel_back)$")),group=1);return client
