import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from clone_plugins.dbusers import clonedb
from plugins.clone import mongo_db
from config import ADMINS


def bot_record(client):
    if mongo_db is None: return {}
    try: return mongo_db.bots.find_one({"bot_id": client.me.id}) or {}
    except Exception: return {}


def owner_only(client, user_id):
    doc = bot_record(client)
    if int(doc.get("user_id", 0)) == int(user_id): return True
    try: return int(user_id) in {int(x) for x in ADMINS}
    except Exception: return False


def save(client, data):
    if mongo_db is not None: mongo_db.bots.update_one({"bot_id": client.me.id}, {"$set": data}, upsert=True)


def back_button(target="my_clone"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data=target)]])


def clone_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("START MSG", callback_data="clone_startmsg"), InlineKeyboardButton("FORCE SUB", callback_data="clone_force")],
        [InlineKeyboardButton("MODERATORS", callback_data="clone_mods"), InlineKeyboardButton("AUTO DELETE", callback_data="clone_autodelete")],
        [InlineKeyboardButton("NO FORWARD", callback_data="clone_noforward"), InlineKeyboardButton("ACCESS TOKEN", callback_data="clone_access")],
        [InlineKeyboardButton("TRANSFER DB", callback_data="clone_transfer"), InlineKeyboardButton("DEACTIVATE", callback_data="clone_deactivate")],
        [InlineKeyboardButton("MODE", callback_data="clone_mode"), InlineKeyboardButton("RESTART", callback_data="clone_restart")],
        [InlineKeyboardButton("STATS", callback_data="clone_stats"), InlineKeyboardButton("DELETE", callback_data="clone_delete")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings")],
    ])


async def settings(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply("⚙️ <b>Settings</b>\n\nCustomize your settings as your need.", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT 🤖", callback_data="my_clone")],
        [InlineKeyboardButton("☁️ GOOGLE BACKUP", callback_data="google_backup")],
        [InlineKeyboardButton("🔗 LINK SHORTENER", callback_data="link_shortener")],
        [InlineKeyboardButton("✏️ CUSTOM CAPTION", callback_data="custom_caption")],
        [InlineKeyboardButton("🟢 CUSTOM BUTTON", callback_data="custom_button")],
        [InlineKeyboardButton("🛡️ PROTECT CONTENT", callback_data="protect_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings_back")],
    ]))


async def force_sub(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2: return await message.reply("Usage: /force_sub @channel or /force_sub off")
    if message.command[1].lower() == "off": save(client, {"force_channels": []}); return await message.reply("✅ Force Subscribe disabled.")
    try:
        chat = await client.get_chat(message.command[1]); channels = list(bot_record(client).get("force_channels", []))
        if chat.id not in channels: channels.append(chat.id)
        save(client, {"force_channels": channels}); await message.reply("✅ Force Subscribe added. Make the bot admin in that channel.")
    except Exception: await message.reply("❌ Cannot access that channel. Make the bot admin first.")


async def caption(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    raw = message.text.split(None, 1)[1] if len(message.command) > 1 else "off"
    if raw.lower() == "off": save(client, {"custom_caption": None}); return await message.reply("✅ Custom caption disabled.")
    save(client, {"custom_caption": raw}); await message.reply("✅ Custom caption saved.")


async def button(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command) < 2 or message.command[1].lower() == "off": save(client, {"custom_buttons": []}); return await message.reply("✅ Custom buttons cleared.")
    raw = message.text.split(None, 1)[1]
    if " - " not in raw: return await message.reply("Usage: /button Text - https://example.com")
    text, url = [x.strip() for x in raw.split(" - ", 1)]
    if not url.startswith(("https://", "http://")): return await message.reply("❌ Button URL must start with http:// or https://")
    buttons = list(bot_record(client).get("custom_buttons", [])); buttons.append({"text": text[:64], "url": url}); save(client, {"custom_buttons": buttons}); await message.reply("✅ Custom button added.")


async def protect(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    value = len(message.command) > 1 and message.command[1].lower() in ("on", "1", "yes", "true")
    save(client, {"protect_content": value}); await message.reply(f"🛡️ Protect Content: <b>{'ON' if value else 'OFF'}</b>")


async def admin_panel(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply("👑 <b>Owner Panel</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("📊 Stats", callback_data="clone_stats")],[InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("🔗 Shortener", callback_data="link_shortener")]]))


async def stats(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply(f"📊 <b>Users:</b> <code>{await clonedb.total_users_count(client.me.id)}</code>")


async def broadcast(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if not message.reply_to_message: return await message.reply("Reply to a message and use /broadcast")
    sent=failed=0
    async for u in clonedb.get_all_users(client.me.id):
        try: await message.reply_to_message.copy(u["user_id"]); sent+=1
        except Exception: failed+=1
        await asyncio.sleep(0.05)
    await message.reply(f"📢 Done\nSent: {sent}\nFailed: {failed}")


async def ban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command)!=2 or not message.command[1].isdigit(): return await message.reply("Usage: /ban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id":int(message.command[1])},{"$set":{"banned":True}},upsert=True); await message.reply("🚫 User banned.")


async def unban(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command)!=2 or not message.command[1].isdigit(): return await message.reply("Usage: /unban USER_ID")
    await clonedb.db[str(client.me.id)].update_one({"user_id":int(message.command[1])},{"$set":{"banned":False}},upsert=True); await message.reply("✅ User unbanned.")


async def auto_delete(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    args=message.command[1:] if len(message.command)>1 else []
    if not args:
        d=bot_record(client); return await message.reply(f"🗑️ <b>Auto Delete</b>\nStatus: {'Enabled ✅' if d.get('auto_delete_enabled') else 'Disabled ❌'}\nTime: {d.get('auto_delete_minutes',15)} minutes\n\nUse /auto_delete on 15 or /auto_delete off")
    if args[0].lower()=="off": save(client,{"auto_delete_enabled":False}); return await message.reply("🗑️ Auto Delete disabled.")
    minutes=15
    if len(args)>1:
        try: minutes=max(1,min(1440,int(args[1])))
        except ValueError: return await message.reply("Usage: /auto_delete on 15")
    save(client,{"auto_delete_enabled":True,"auto_delete_minutes":minutes}); await message.reply(f"🗑️ Auto Delete enabled for {minutes} minutes.")


async def no_forward(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    d=bot_record(client); value=bool(d.get("no_forward",False)) if len(message.command)==1 else message.command[1].lower() in ("on","1","yes","true")
    save(client,{"no_forward":value}); await message.reply(f"🚫 No Forward: <b>{'Enabled ✅' if value else 'Disabled ❌'}</b>")


async def moderators(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    mods=[int(x) for x in bot_record(client).get("moderators",[]) if str(x).isdigit()]
    if len(message.command)==1: return await message.reply("👮 <b>Moderators</b>\n\n"+("\n".join(f"• <code>{x}</code>" for x in mods) if mods else "No moderators.")+"\n\nUse /moderator add USER_ID or /moderator del USER_ID")
    if len(message.command)!=3 or not message.command[2].isdigit(): return await message.reply("Usage: /moderator add USER_ID")
    uid=int(message.command[2])
    if message.command[1].lower()=="add" and uid not in mods: mods.append(uid)
    elif message.command[1].lower()=="del": mods=[x for x in mods if x!=uid]
    else: return await message.reply("Usage: /moderator add USER_ID or /moderator del USER_ID")
    save(client,{"moderators":mods}); await message.reply("✅ Moderator list updated.")


async def access_token(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    d=bot_record(client)
    if len(message.command)==1: return await message.reply(f"🔑 <b>Access Token</b>\n\nStatus: {'Enabled ✅' if d.get('access_token_enabled',True) else 'Disabled ❌'}\nValidity: {d.get('access_token_hours',1)} hour(s)\nRenewed: 0 users\n\nUse /access_token on 1 or /access_token off")
    if message.command[1].lower()=="off": save(client,{"access_token_enabled":False}); return await message.reply("🔑 Access Token disabled.")
    hours=1
    if len(message.command)>2:
        try: hours=max(1,min(168,int(message.command[2])))
        except ValueError: return await message.reply("Usage: /access_token on 1")
    save(client,{"access_token_enabled":True,"access_token_hours":hours}); await message.reply(f"🔑 Access Token enabled. Validity: {hours} hour(s).")


async def transfer_db(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command)<2 or not message.command[1].isdigit(): return await message.reply("Usage: /transfer_db OLD_BOT_ID")
    old_id=int(message.command[1]); new_id=client.me.id
    if old_id==new_id: return await message.reply("❌ Old and new bot IDs are the same.")
    try:
        docs=await clonedb.get_all_users(old_id).to_list(length=None); inserted=0
        for doc in docs:
            doc.pop("_id",None); await clonedb.db[str(new_id)].update_one({"user_id":doc["user_id"]},{"$set":doc},upsert=True); inserted+=1
        await message.reply(f"✅ Transfer complete.\nUsers transferred: {inserted}")
    except Exception as e: await message.reply(f"❌ Transfer failed: <code>{e}</code>")


async def deactivate(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if len(message.command)==1:
        d=bot_record(client); return await message.reply(f"⏸ <b>Deactivate</b>\nStatus: {'Deactivated' if d.get('deactivated') else 'Active'}\n\nUse /deactivate on or /deactivate off")
    value=message.command[1].lower() in ("on","1","yes","true"); save(client,{"deactivated":value}); await message.reply("⏸ Clone deactivated." if value else "▶️ Clone activated.")


async def mode(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    d=bot_record(client); current=d.get("mode","private")
    if len(message.command)>1:
        current=message.command[1].lower()
        if current not in ("private","public"): return await message.reply("Usage: /mode public or /mode private")
        save(client,{"mode":current})
    await message.reply(f"🔒 <b>Clone Mode: {current.title()}</b>\n\nPublic: any Telegram user can generate shareable links.\nPrivate: only owner/moderators can generate them.")


async def restart(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    save(client,{"restart_requested":True}); await message.reply("🔄 Settings saved. Restart the service to reload this clone.")


async def delete_clone(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    await message.reply("⚠️ <b>Delete Clone</b>\n\nThis removes the clone record from the manager database. It does not delete the bot from BotFather.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("YES, DELETE",callback_data="delete_confirm"),InlineKeyboardButton("CANCEL",callback_data="my_clone")]]))


async def startmsg(client, message):
    if not owner_only(client, message.from_user.id): return await message.reply("❌ Owner only.")
    if not message.reply_to_message: return await message.reply("Reply to a message/photo and use /start_msg to save it.")
    txt=message.reply_to_message.text or message.reply_to_message.caption or ""; save(client,{"start_message":txt[:4000]}); await message.reply("✅ Start message saved.")


async def clone_callback(client, query):
    data=query.data
    if data=="my_clone": return await query.message.edit_text(f"🛠 <b>Customize Clone</b>\n\n➜ <b>Name:</b> {client.me.first_name}\n\nConfigure Your Clone Settings Using Given Buttons",reply_markup=clone_menu())
    allowed=data.startswith(("clone_","autodelete_","noforward_","access_","mode_","hide_owner")) or data in ("delete_confirm",)
    if not allowed: return
    if not owner_only(client,query.from_user.id): return await query.answer("Owner only.",show_alert=True)
    d=bot_record(client)
    if data=="clone_startmsg": return await query.message.edit_text("📝 <b>Start Message</b>\n\nReply to any message/photo and use <code>/start_msg</code> to save its text/caption.",reply_markup=back_button())
    if data=="clone_force": return await query.message.edit_text("📢 <b>Force Subscribe</b>\n\nConfigured channels: <code>%s</code>\n\nUse <code>/force_sub @channel</code> to add.\nUse <code>/force_sub off</code> to clear."%len(d.get("force_channels",[])),reply_markup=back_button())
    if data=="clone_mods":
        mods=d.get("moderators",[]); return await query.message.edit_text("👮 <b>Moderators</b>\n\n"+("\n".join(f"• <code>{x}</code>" for x in mods) if mods else "No moderators.")+"\n\n<code>/moderator add USER_ID</code>\n<code>/moderator del USER_ID</code>",reply_markup=back_button())
    if data=="clone_autodelete": return await query.message.edit_text("🗑️ <b>Auto Delete</b>\n\nStatus: %s\nTime: %s minutes"%(('Enabled ✅' if d.get('auto_delete_enabled') else 'Disabled ❌'),d.get('auto_delete_minutes',15)),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("15 MIN",callback_data="autodelete_15"),InlineKeyboardButton("30 MIN",callback_data="autodelete_30")],[InlineKeyboardButton("1 HOUR",callback_data="autodelete_60"),InlineKeyboardButton("DISABLE ❌",callback_data="autodelete_off")],[InlineKeyboardButton("‹ BACK",callback_data="my_clone")]]))
    if data=="clone_noforward": return await query.message.edit_text("🚫 <b>No Forward</b>\n\nRestrict clone users from forwarding messages from shareable links.\n\nStatus: %s"%('Enabled ✅' if d.get('no_forward') else 'Disabled ❌'),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Enable",callback_data="noforward_on"),InlineKeyboardButton("Disable ❌",callback_data="noforward_off")],[InlineKeyboardButton("‹ BACK",callback_data="my_clone")]]))
    if data=="clone_access": return await query.message.edit_text("🔑 <b>Access Token</b>\n\nUsers need to pass a shortened link to gain special access to messages from clone shareable links.\n\nStatus: %s\nValidity: %s hour(s)\nRenewed: 0 users"%(('Enabled ✅' if d.get('access_token_enabled',True) else 'Disabled ❌'),d.get('access_token_hours',1)),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("SHORTENERS",callback_data="access_shorteners"),InlineKeyboardButton("VALIDITY",callback_data="access_validity")],[InlineKeyboardButton("TUTORIAL",callback_data="access_tutorial"),InlineKeyboardButton("WHITELISTERS",callback_data="access_whitelist")],[InlineKeyboardButton("REFERRAL",callback_data="access_referral")],[InlineKeyboardButton("‹ BACK",callback_data="my_clone")]]))
    if data=="clone_transfer": return await query.message.edit_text("🔄 <b>Transfer Users</b>\n\nTransfer users from another clone using the same MongoDB database.\n\nUse <code>/transfer_db OLD_BOT_ID</code>.",reply_markup=back_button())
    if data=="clone_deactivate": return await query.message.edit_text("⏸ <b>Deactivate</b>\n\nCurrent: %s\n\nUse <code>/deactivate on</code> or <code>/deactivate off</code>."%('Deactivated' if d.get('deactivated') else 'Active'),reply_markup=back_button())
    if data=="clone_mode": return await query.message.edit_text("🔒 <b>Clone Mode</b>\n\nPublic Mode: any Telegram user can generate shareable and short links.\nPrivate Mode: only owner/moderators can generate them.\n\nCurrent Mode: <b>%s</b>"%d.get('mode','private').title(),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Make Public",callback_data="mode_public")],[InlineKeyboardButton("Make Private",callback_data="mode_private")],[InlineKeyboardButton("HIDE OWNER",callback_data="hide_owner")],[InlineKeyboardButton("‹ BACK",callback_data="my_clone")]]))
    if data=="clone_restart": save(client,{"restart_requested":True}); return await query.message.edit_text("🔄 <b>Successfully Saved Clone Bot Settings</b>\n\nSaved settings will be reloaded automatically when the clone restarts.",reply_markup=back_button())
    if data=="clone_stats":
        count=await clonedb.total_users_count(client.me.id); return await query.message.edit_text(f"📊 <b>FILE STORE BOT</b>\n\n◇ Total Users: <code>{count}</code>\n◇ Banned Users: <code>{d.get('banned_count',0)}</code>",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("OK",callback_data="my_clone")]]))
    if data=="clone_delete": return await query.message.edit_text("⚠️ <b>Delete Clone</b>\n\nThis removes the clone record from the manager database.\nIt does not delete the bot from BotFather.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("YES, DELETE",callback_data="delete_confirm"),InlineKeyboardButton("CANCEL",callback_data="my_clone")]]))
    if data=="delete_confirm":
        if mongo_db is not None: mongo_db.bots.delete_one({"bot_id":client.me.id})
        return await query.message.edit_text("🗑️ <b>Clone record deleted.</b>")
    if data.startswith("autodelete_"):
        value=data.split("_",1)[1]
        if value=="off": save(client,{"auto_delete_enabled":False}); text="🗑️ Auto Delete disabled."
        else: save(client,{"auto_delete_enabled":True,"auto_delete_minutes":int(value)}); text=f"🗑️ Auto Delete enabled for {value} minutes."
        return await query.message.edit_text(text,reply_markup=back_button())
    if data.startswith("noforward_"):
        value=data.endswith("_on"); save(client,{"no_forward":value}); return await query.message.edit_text(f"🚫 No Forward: <b>{'Enabled ✅' if value else 'Disabled ❌'}</b>",reply_markup=back_button())
    if data=="access_shorteners": return await query.message.edit_text("🔗 <b>Access Token Shorteners</b>\n\nConfigure Link Shortener from Settings. Use /api KEY and /base_site example.com.",reply_markup=back_button("clone_access"))
    if data=="access_validity": return await query.message.edit_text("⏱ <b>Access Token Validity</b>\n\nChoose validity:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("1 HOUR",callback_data="access_hours_1"),InlineKeyboardButton("6 HOURS",callback_data="access_hours_6")],[InlineKeyboardButton("24 HOURS",callback_data="access_hours_24"),InlineKeyboardButton("7 DAYS",callback_data="access_hours_168")],[InlineKeyboardButton("‹ BACK",callback_data="clone_access")]]))
    if data.startswith("access_hours_"):
        hours=int(data.rsplit("_",1)[1]); save(client,{"access_token_enabled":True,"access_token_hours":hours}); return await query.message.edit_text(f"✅ Access Token validity set to {hours} hour(s).",reply_markup=back_button("clone_access"))
    if data=="access_tutorial": return await query.message.edit_text("📖 <b>Access Token Tutorial</b>\n\n1. Configure a shortener.\n2. Enable Access Token.\n3. Set validity.\n4. Users complete shortener verification before protected access.",reply_markup=back_button("clone_access"))
    if data=="access_whitelist": return await query.message.edit_text("📝 <b>Whitelisters</b>\n\nOwner and moderators are automatically allowed. Use the moderator menu to add trusted users.",reply_markup=back_button("clone_access"))
    if data=="access_referral": return await query.message.edit_text("👥 <b>Referral</b>\n\nReferral statistics are not connected to an external referral service yet.",reply_markup=back_button("clone_access"))
    if data in ("mode_public","mode_private"):
        mode_value="public" if data.endswith("public") else "private"; save(client,{"mode":mode_value}); return await query.message.edit_text(f"🔒 Clone mode changed to <b>{mode_value.title()}</b>.",reply_markup=back_button())
    if data=="hide_owner": save(client,{"hide_owner":True}); return await query.answer("Owner hidden from clone information.",show_alert=True)
    return await query.answer("Unknown option.",show_alert=True)


def register(client):
    private=filters.private
    for fn,cmd in [(settings,"settings"),(force_sub,"force_sub"),(caption,"caption"),(button,"button"),(protect,"protect"),(admin_panel,"admin"),(stats,"stats"),(broadcast,"broadcast"),(ban,"ban"),(unban,"unban"),(auto_delete,"auto_delete"),(no_forward,"no_forward"),(moderators,"moderator"),(access_token,"access_token"),(transfer_db,"transfer_db"),(deactivate,"deactivate"),(mode,"mode"),(restart,"restart"),(delete_clone,"delete"),(startmsg,"start_msg")]:
        client.add_handler(MessageHandler(fn,filters.command(cmd)&private),group=1)
    regex=r"^(my_clone|google_backup|link_shortener|custom_caption|custom_button|protect_menu|protect_on|protect_off|settings|settings_back|clone_.*|delete_confirm|autodelete_.*|noforward_.*|access_.*|mode_.*|hide_owner|admin_.*)$"
    client.add_handler(CallbackQueryHandler(clone_callback,filters.regex(regex)),group=1)
    return client
