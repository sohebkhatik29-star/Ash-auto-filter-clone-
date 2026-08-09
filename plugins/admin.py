from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import ADMINS
from plugins.dbusers import db
from plugins.clone import mongo_db


def admin_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton("🤖 Cloned Bots", callback_data="admin_clones"),
        ],
        [InlineKeyboardButton("📢 Broadcast Help", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


@Client.on_message(filters.command("admin") & filters.private & filters.user(ADMINS))
async def admin_panel(client, message):
    await message.reply_text(
        "<b>⚙️ ADMIN PANEL</b>\n\nChoose an option below:",
        reply_markup=admin_markup(),
    )


@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def admin_stats_command(client, message):
    users = await db.total_users_count()
    clones = await mongo_db.bots.count_documents({})
    await message.reply_text(
        f"<b>📊 BOT STATISTICS</b>\n\n"
        f"👥 Users: <code>{users}</code>\n"
        f"🤖 Cloned bots: <code>{clones}</code>"
    )


@Client.on_callback_query(filters.regex(r"^admin_(stats|clones|broadcast|close)$"))
async def admin_callbacks(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        await query.answer("Not authorized.", show_alert=True)
        return

    if query.data == "admin_close":
        await query.message.delete()
        return

    if query.data == "admin_stats":
        users = await db.total_users_count()
        clones = await mongo_db.bots.count_documents({})
        await query.answer()
        await query.message.edit_text(
            f"<b>📊 BOT STATISTICS</b>\n\n"
            f"👥 Users: <code>{users}</code>\n"
            f"🤖 Cloned bots: <code>{clones}</code>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
                [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
            ])
        )
        return

    if query.data == "admin_clones":
        clones = await mongo_db.bots.count_documents({})
        await query.answer()
        await query.message.edit_text(
            f"<b>🤖 CLONED BOTS</b>\n\nTotal: <code>{clones}</code>\n\n"
            "Use <code>/deletecloned</code> to remove a clone from the database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
                [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
            ])
        )
        return

    if query.data == "admin_broadcast":
        await query.answer()
        await query.message.edit_text(
            "<b>📢 BROADCAST</b>\n\n"
            "Reply to the message you want to send and use:\n"
            "<code>/broadcast</code>\n\n"
            "This command is restricted to ADMINS.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
                [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
            ])
        )
        return

    if query.data == "admin_back":
        await query.answer()
        await query.message.edit_text(
            "<b>⚙️ ADMIN PANEL</b>\n\nChoose an option below:",
            reply_markup=admin_markup(),
        )
