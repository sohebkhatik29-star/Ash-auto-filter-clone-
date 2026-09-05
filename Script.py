class script(object):
    START_TXT = """<b>ʜᴇʟʟᴏ {}, ᴍʏ ɴᴀᴍᴇ {} 👋, ɪ ᴀᴍ ʟᴀᴛᴇꜱᴛ ᴀᴅᴠᴀɴᴄᴇᴅ ᴀɴᴅ ᴘᴏᴡᴇʀꜰᴜʟ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ + ᴄʟᴏɴᴇ ғᴇᴀᴛᴜʀᴇ + sᴛʀᴇᴀᴍ / ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ ғᴇᴀᴛᴜʀᴇ + ᴄᴜsᴛᴏᴍ ᴜʀʟ sʜᴏʀᴛᴇɴᴇʀ sᴜᴘᴘᴏʀᴛ + ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ sᴜᴘᴘᴏʀᴛ ᴀɴᴅ ʙᴇsᴛ ᴜɪ ᴘᴇʀғᴏʀᴍᴀɴᴄᴇ </b>"""

    CAPTION = """<b>📂 ғɪʟᴇɴᴀᴍᴇ : {file_name}
⚙️ sɪᴢᴇ : {file_size}
Jᴏɪɴ [ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ](https://t.me/MoviesGroupG3)</b>"""

    SHORTENER_API_MESSAGE = """<b>Tᴏ ᴀᴅᴅ ᴏʀ ᴜᴘᴅᴀᴛᴇ ʏᴏᴜʀ Sʜᴏʀᴛᴇɴᴇʀ Wᴇʙsɪᴛᴇ API, /api (ᴀᴘɪ)
Ex: /api ʏᴏᴜʀ_ᴀᴘɪ_ᴋᴇʏ
Cᴜʀʀᴇɴᴛ Wᴇʙsɪᴛᴇ: {base_site}
Cᴜʀʀᴇɴᴛ Sʜᴏʀᴛᴇɴᴇʀ API:</b> `{shortener_api}`
If You Want To Remove Api Then Copy This And Send To Bot - `/api None`"""

    CLONE_START_TXT = """<b>ʜᴇʟʟᴏ {}, ᴍʏ ɴᴀᴍᴇ {} 👋, ɪ ᴀᴍ ᴀɴ ᴀᴅᴠᴀɴᴄᴇᴅ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ ᴡɪᴛʜ ᴄᴜsᴛᴏᴍ ᴜʀʟ sʜᴏʀᴛᴇɴᴇʀ ᴀɴᴅ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ.ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ ᴛʜᴇɴ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ ғʀᴏᴍ ᴛʜɪs ᴘᴀʀᴇɴᴛ ʙᴏᴛ.</b>"""

    ABOUT_TXT = """✨ <b><u>ABOUT ME</u></b>

☆ <b>MY NAME:</b> {}

☆ <b>CLONE OF:</b> <a href=https://t.me/{}>{}</a>

☆ <b>MY OWNER:</b> <a href=tg://user?id={}>{}</a>

☆ <b>UPDATES:</b> <a href=https://t.me/MoviesGroupG3>ASH BOTZ</a>

☆ <b>SUPPORT:</b> <a href=https://t.me/ash_movie_j>ASH GROUP</a>

☆ <b>VERSION:</b> 0.7.19 [V1.6]"""

    CABOUT_TXT = """✨ <b><u>ABOUT ME</u></b>

☆ <b>MY NAME:</b> {}

☆ <b>CLONE OF:</b> <a href=https://t.me/{}>{}</a>

☆ <b>MY OWNER:</b> <a href=tg://user?id={}>{}</a>

☆ <b>UPDATES:</b> <a href=https://t.me/MoviesGroupG3>ASH BOTZ</a>

☆ <b>SUPPORT:</b> <a href=https://t.me/ash_movie_j>ASH GROUP</a>

☆ <b>VERSION:</b> 0.7.19 [V1.6]"""

    CLONE_TXT = """<b>ʜᴇʟʟᴏ {} 👋
First Send /clone command then follow below steps.
1) sᴇɴᴅ <code>/newbot</code> ᴛᴏ @BotFather
2) ɢɪᴠᴇ ᴀ ɴᴀᴍᴇ ғᴏʀ ʏᴏᴜʀ ʙᴏᴛ.
3) ɢɪᴠᴇ ᴀ ᴜɴɪǫᴜᴇ ᴜsᴇʀɴᴀᴍᴇ.
4) ᴛʜᴇɴ ʏᴏᴜ ᴡɪʟʟ ɢᴇᴛ ᴀ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ʏᴏᴜʀ ʙᴏᴛ ᴛᴏᴋᴇɴ.
5) ꜰᴏʀᴡᴀʀᴅ ᴛʜᴀᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴍᴇ.
ᴛʜᴇɴ ɪ ᴡɪʟʟ ᴛʀʏ ᴛᴏ ᴄʀᴇᴀᴛᴇ ᴀ ᴄʟᴏɴᴇ ʙᴏᴛ ғᴏʀ ʏᴏᴜ 😌</b>"""

    HELP_TXT = """🌵 <b>Help Menu</b>

I am a permanent file store bot. You can store files from your public channel without making me admin. For private channel or group, make me admin first. Use below commands to store and access your files via shareable link.

📚 <b>Available Commands:</b>
➜ /start - check i am alive.
➜ /genlink - To store a single message or file (moderators only).
➜ /batch - To store multiple messages from a channel (moderators only).
➜ /custom_batch - To store multiple random messages (moderators only).
➜ /shortener - To shorten any shareable links (moderators only).
➜ /settings - Customize your settings as needed.
 
🛡️ <b>Moderators Commands:</b>
➜ /special_link - store multiple messages and get an editable link.
➜ /universal_link - stores multiple messages that can be accessed from any of your clones.
➜ /broadcast - Broadcast messages to users.
➜ /an_broadcast - Broadcast messages without pin / unpin notification.
➜ /ban - ban a user.
➜ /unban - unban a user."""

    CHELP_TXT = HELP_TXT

    LOG_TEXT = """<b>#NewUserID - <code>{}</code>
Nᴀᴍᴇ - {}</b>"""

    RESTART_TXT = """<b>Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ !
📅 Dᴀᴛᴇ : <code>{}</code>
⏰ Tɪᴍᴇ : <code>{}</code>
🌐 Tɪᴍᴇᴢᴏɴᴇ : <code>Asia/Kolkata</code>
🛠️ Bᴜɪʟᴅ Sᴛᴀᴛᴜs: <code>ASH FILE STORE [ Sᴛᴀʙʟᴇ ]</code></b>"""
