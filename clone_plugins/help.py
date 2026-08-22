from pyrogram import Client, filters

HELP_TEXT = """<b>📚 Clone Bot Help</b>

<b>👤 File & Link</b>
/start - Start / open a stored link
/link - Create a file link
genlink - Generate a file link
/batch - Create a batch link
/custom_batch - Custom batch
/special_link - Special link
/universal_link - Universal link
/shortener - Shortener settings

<b>⚙️ Owner Settings</b>
/settings - View settings
/force_sub - Add a force-join channel
/caption - Set custom caption
/button - Add a custom button
/api - Set shortener API
/base_site - Set shortener base site

<b>👑 Owner</b>
/admin - Owner panel
/stats - Bot statistics
/broadcast - Broadcast
/ban - Ban user
/unban - Unban user
"""

@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    await message.reply_text(HELP_TEXT)
