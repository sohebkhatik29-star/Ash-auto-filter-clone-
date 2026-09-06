from pyrogram import Client, filters
from config import ADMINS
from settings_modules.master_admin_panel import is_master_admin, admin_panel_main_markup, db, get_all_admins

@Client.on_message(filters.command(["admin", "stats"]) & filters.private)
async def admin_panel(client, message):
    user_id = message.from_user.id
    if not is_master_admin(user_id):
        return await message.reply("❌ <b>Access denied.</b> Master Bot Admins only.")

    m = db()
    total_master_users = 0
    try:
        from plugins.dbusers import db as u_db
        total_master_users = await u_db.total_users_count()
    except Exception:
        pass

    total_bots = 0
    active_bots = 0
    inactive_bots = 0
    total_owners = 0
    if m is not None:
        total_bots = m.bots.count_documents({})
        inactive_bots = m.bots.count_documents({"$or": [{"deactivated": True}, {"suspended": True}]})
        active_bots = total_bots - inactive_bots
        try:
            total_owners = len(m.bots.distinct("user_id"))
        except Exception:
            agg = list(m.bots.aggregate([{"$group": {"_id": "$user_id"}}, {"$count": "total"}]))
            total_owners = agg[0]["total"] if agg else 0
    admin_count = len(get_all_admins())

    text = (
        "👑 <b>MASTER BOT ADMIN CONTROL PANEL</b>\n\n"
        "<blockquote>Welcome Administrator! Control and supervise all cloned bots, search clone owners, monitor live system status, and configure bot settings.</blockquote>\n\n"
        f"👤 <b>MASTER BOT USERS:</b> <code>{total_master_users:,} Users</code>\n"
        f"👑 <b>TOTAL CLONE OWNERS:</b> <code>{total_owners:,} Users</code>\n"
        f"🤖 <b>TOTAL CLONED BOTS:</b> <code>{total_bots:,} Bots</code>\n"
        f"  ├ 🟢 <b>Active Clones:</b> <code>{active_bots:,}</code>\n"
        f"  └ 🔴 <b>Stopped / Deactivated:</b> <code>{inactive_bots:,}</code>\n\n"
        f"👮 <b>MASTER BOT ADMINS:</b> <code>{admin_count} Admins</code>\n\n"
        "<i>Select an option from the menu below:</i>"
    )
    return await message.reply_text(text, reply_markup=admin_panel_main_markup())
