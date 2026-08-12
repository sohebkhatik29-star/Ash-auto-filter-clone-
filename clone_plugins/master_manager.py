from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.clone import mongo_db
from config import ADMINS


def is_admin(uid):
    try: return int(uid) in {int(x) for x in ADMINS}
    except Exception: return False

def docs_for(uid):
    if mongo_db is None: return []
    q = {} if is_admin(uid) else {"user_id": int(uid)}
    return list(mongo_db.bots.find(q, {"token": 0}).sort("bot_id", 1))

def owns(uid, bid):
    return is_admin(uid) or bool(mongo_db and mongo_db.bots.find_one({"bot_id": int(bid), "user_id": int(uid)}))

def list_markup(docs):
    rows=[]
    for d in docs:
        bid=int(d["bot_id"]); name=d.get("name") or d.get("username") or str(bid)
        rows.append([InlineKeyboardButton(f"🤖 {name[:32]}", callback_data=f"manage_clone:{bid}")])
    rows.append([InlineKeyboardButton("‹ BACK", callback_data="settings")])
    return InlineKeyboardMarkup(rows)

def manage_markup(bid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 START MSG",callback_data=f"cm:{bid}:startmsg"),InlineKeyboardButton("📢 FORCE SUB",callback_data=f"cm:{bid}:force")],
        [InlineKeyboardButton("👮 MODERATORS",callback_data=f"cm:{bid}:mods"),InlineKeyboardButton("🗑 AUTO DELETE",callback_data=f"cm:{bid}:autodelete")],
        [InlineKeyboardButton("🚫 NO FORWARD",callback_data=f"cm:{bid}:noforward"),InlineKeyboardButton("🔑 ACCESS TOKEN",callback_data=f"cm:{bid}:access")],
        [InlineKeyboardButton("🔄 TRANSFER DB",callback_data=f"cm:{bid}:transfer"),InlineKeyboardButton("⏸ DEACTIVATE",callback_data=f"cm:{bid}:deactivate")],
        [InlineKeyboardButton("🔒 MODE",callback_data=f"cm:{bid}:mode"),InlineKeyboardButton("🔄 RESTART",callback_data=f"cm:{bid}:restart")],
        [InlineKeyboardButton("📊 STATS",callback_data=f"cm:{bid}:stats"),InlineKeyboardButton("🗑 DELETE",callback_data=f"cm:{bid}:delete")],
        [InlineKeyboardButton("‹ BACK",callback_data="my_clones")]
    ])

@Client.on_callback_query(filters.regex(r"^my_clones$"))
async def my_clones(client, query):
    docs=docs_for(query.from_user.id)
    if not docs: return await query.answer("No clones found for your account.",show_alert=True)
    await query.message.edit_text("🤖 <b>MY CLONE BOT</b>\n\nSelect your clone:",reply_markup=list_markup(docs)); await query.answer()

@Client.on_callback_query(filters.regex(r"^manage_clone:\d+$"))
async def manage_clone(client, query):
    bid=int(query.data.split(":")[1])
    if not owns(query.from_user.id,bid): return await query.answer("❌ You can manage only your own clones.",show_alert=True)
    d=mongo_db.bots.find_one({"bot_id":bid}) or {}; title=d.get("name") or d.get("username") or str(bid)
    await query.message.edit_text(f"🛠 <b>Customize Clone</b>\n\n🤖 {title}\n\nChoose what you want to manage:",reply_markup=manage_markup(bid)); await query.answer()

@Client.on_callback_query(filters.regex(r"^cm:\d+:(startmsg|force|mods|autodelete|noforward|access|transfer|deactivate|mode|restart|stats|delete)$"))
async def clone_manage_action(client, query):
    _,raw,action=query.data.split(":"); bid=int(raw)
    if not owns(query.from_user.id,bid): return await query.answer("❌ Access denied.",show_alert=True)
    d=mongo_db.bots.find_one({"bot_id":bid}) or {}; back=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK",callback_data=f"manage_clone:{bid}")]])
    if action=="startmsg": text="📝 <b>START MESSAGE</b>\n\n"+(d.get("start_message") or "Not configured")
    elif action=="force": text=f"📢 <b>FORCE SUB</b>\n\nChannels configured: <code>{len(d.get('force_channels',[]))}</code>"
    elif action=="mods": text="👮 <b>MODERATORS</b>\n\n"+(("\n".join(f"• <code>{x}</code>" for x in d.get("moderators",[]))) or "No moderators configured.")
    elif action=="autodelete": text=f"🗑️ <b>AUTO DELETE</b>\n\nStatus: {'ON' if d.get('auto_delete_enabled') else 'OFF'}\nTime: {d.get('auto_delete_minutes',15)} minutes"
    elif action=="noforward": text=f"🚫 <b>NO FORWARD</b>\n\nStatus: {'ON' if d.get('no_forward') else 'OFF'}"
    elif action=="access": text=f"🔑 <b>ACCESS TOKEN</b>\n\nStatus: {'ON' if d.get('access_token_enabled',True) else 'OFF'}\nValidity: {d.get('access_token_hours',1)} hour(s)"
    elif action=="transfer": text="🔄 <b>TRANSFER DB</b>\n\nUse the transfer workflow for this selected clone."
    elif action=="deactivate": text=f"⏸ <b>DEACTIVATE</b>\n\nStatus: {'Deactivated' if d.get('deactivated') else 'Active'}"
    elif action=="mode": text=f"🔒 <b>MODE</b>\n\nCurrent: {d.get('mode','private').title()}"
    elif action=="restart": mongo_db.bots.update_one({"bot_id":bid},{"$set":{"restart_requested":True}}); text="🔄 <b>Restart requested.</b>\n\nSaved settings will load when this clone restarts."
    elif action=="stats": text=f"📊 <b>CLONE STATS</b>\n\nBot ID: <code>{bid}</code>\nUsers: <code>{d.get('user_count',0)}</code>"
    else: text="⚠️ <b>DELETE CLONE</b>\n\nThis removes the clone record from the manager database."; back=InlineKeyboardMarkup([[InlineKeyboardButton("YES, DELETE",callback_data=f"cmdelete:{bid}"),InlineKeyboardButton("CANCEL",callback_data=f"manage_clone:{bid}")]])
    await query.message.edit_text(text,reply_markup=back); await query.answer()

@Client.on_callback_query(filters.regex(r"^cmdelete:\d+$"))
async def clone_delete(client, query):
    bid=int(query.data.split(":")[1])
    if not owns(query.from_user.id,bid): return await query.answer("❌ Access denied.",show_alert=True)
    mongo_db.bots.delete_one({"bot_id":bid}); await query.message.edit_text("🗑️ <b>Clone removed from the manager database.</b>"); await query.answer("Deleted")
