from pyrogram import filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.handlers import StopPropagation
from config import ADMINS
from clone_plugins.master_manager import docs_for, list_markup, manage_clone, clone_manage_action, clone_delete


def is_admin(uid):
    try:
        return int(uid) in {int(x) for x in ADMINS}
    except Exception:
        return False


def master_settings_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT 🤖", callback_data="my_clone")],
        [InlineKeyboardButton("☁️ GOOGLE BACKUP", callback_data="master_google_backup")],
    ])


async def settings(client, message):
    await message.reply_text(
        "⚙️ <b>MASTER SETTINGS</b>\n\n"
        "Manage your own clone bots from here.\n"
        "You will only see clones that belong to your Telegram account.",
        reply_markup=master_settings_markup(),
    )
    raise StopPropagation


async def callbacks(client, query):
    data = query.data or ""

    if data == "my_clone":
        docs = docs_for(query.from_user.id)
        if not docs:
            await query.answer("You have no clones yet. Use /clone first.", show_alert=True)
            raise StopPropagation
        await query.message.edit_text(
            "🤖 <b>MY CLONE BOT</b>\n\nSelect your clone:",
            reply_markup=list_markup(docs),
        )
        await query.answer()
        raise StopPropagation

    if data == "master_google_backup":
        await query.message.edit_text(
            "☁️ <b>Google Backup</b>\n\n"
            "Google Drive backup is not configured yet. Clone settings and ownership are stored in MongoDB.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="master_settings")]]),
        )
        await query.answer()
        raise StopPropagation

    if data == "master_settings":
        await query.message.edit_text(
            "⚙️ <b>MASTER SETTINGS</b>\n\nManage your own clone bots from here.",
            reply_markup=master_settings_markup(),
        )
        await query.answer()
        raise StopPropagation

    if data.startswith("manage_clone:"):
        await manage_clone(client, query)
        raise StopPropagation

    if data.startswith("cm:"):
        await clone_manage_action(client, query)
        raise StopPropagation

    if data.startswith("cmdelete:"):
        await clone_delete(client, query)
        raise StopPropagation

    if data == "my_clones":
        docs = docs_for(query.from_user.id)
        if not docs:
            await query.answer("No clones found.", show_alert=True)
            raise StopPropagation
        await query.message.edit_text("🤖 <b>MY CLONE BOT</b>\n\nSelect your clone:", reply_markup=list_markup(docs))
        await query.answer()
        raise StopPropagation


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=0)
    client.add_handler(
        CallbackQueryHandler(
            callbacks,
            filters.regex(r"^(my_clone|my_clones|manage_clone:\d+|cm:\d+:[a-z_]+|cmdelete:\d+|master_google_backup|master_settings)$"),
        ),
        group=-1,
    )
