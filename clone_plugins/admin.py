from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from plugins.clone import mongo_db
from clone_plugins.dbusers import clonedb


def get_owner_id(bot_id):
    record = mongo_db.bots.find_one({"bot_id": bot_id})
    return int(record["user_id"]) if record and record.get("user_id") else None


def panel_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Statistics", callback_data="cadmin_stats"),
            InlineKeyboardButton("🤖 Bot Info", callback_data="cadmin_info"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="cadmin_close")],
    ])


async def is_owner(client, user_id):
    me = await client.get_me()
    owner_id = get_owner_id(me.id)
    return owner_id == user_id


@Client.on_message(filters.command("admin") & filters.private)
async def clone_admin(client, message):
    if not await is_owner(client, message.from_user.id):
        await message.reply_text("<b>⛔ Admin access only.</b>")
        return
    await message.reply_text(
        "<b>⚙️ CLONE BOT ADMIN PANEL</b>\n\nChoose an option below:",
        reply_markup=panel_markup(),
    )


@Client.on_message(filters.command("stats") & filters.private)
async def clone_stats(client, message):
    if not await is_owner(client, message.from_user.id):
        await message.reply_text("<b>⛔ Admin access only.</b>")
        return
    me = await client.get_me()
    users = await clonedb.total_users_count(me.id)
    await message.reply_text(
        f"<b>📊 CLONE BOT STATISTICS</b>\n\n"
        f"👥 Users: <code>{users}</code>\n"
        f"🤖 Bot: @{me.username}"
    )


@Client.on_callback_query(filters.regex(r"^cadmin_(stats|info|close)$"))
async def clone_admin_callbacks(client, query: CallbackQuery):
    if not await is_owner(client, query.from_user.id):
        await query.answer("Admin access only.", show_alert=True)
        return

    if query.data == "cadmin_close":
        await query.message.delete()
        return

    me = await client.get_me()
    users = await clonedb.total_users_count(me.id)

    if query.data == "cadmin_stats":
        await query.answer()
        text = (
            "<b>📊 CLONE BOT STATISTICS</b>\n\n"
            f"👥 Users: <code>{users}</code>\n"
            f"🤖 Bot: @{me.username}"
        )
    else:
        await query.answer()
        text = (
            "<b>🤖 BOT INFO</b>\n\n"
            f"Name: <code>{me.first_name}</code>\n"
            f"Username: <code>@{me.username}</code>\n"
            f"Bot ID: <code>{me.id}</code>\n"
            f"Users: <code>{users}</code>"
        )

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="cadmin_back")],
            [InlineKeyboardButton("❌ Close", callback_data="cadmin_close")],
        ])
    )


@Client.on_callback_query(filters.regex(r"^cadmin_back$"))
async def clone_admin_back(client, query: CallbackQuery):
    if not await is_owner(client, query.from_user.id):
        await query.answer("Admin access only.", show_alert=True)
        return
    await query.answer()
    await query.message.edit_text(
        "<b>⚙️ CLONE BOT ADMIN PANEL</b>\n\nChoose an option below:",
        reply_markup=panel_markup(),
    )
