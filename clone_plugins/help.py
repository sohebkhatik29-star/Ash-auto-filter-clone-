from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Script import script

@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    try:
        from clone_plugins.ban_manager import check_user_banned_or_block
        if await check_user_banned_or_block(client, message):
            return
    except Exception:
        pass
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("‹ BACK", callback_data="start_back")]])
    await message.reply_text(script.HELP_TXT, reply_markup=markup, disable_web_page_preview=True)
