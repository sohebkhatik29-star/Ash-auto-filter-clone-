"""Universal Link generator handler.
Main command: /universal_link
"""
import secrets
import time
from pyrogram import StopPropagation, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from clone_plugins.commands import bot_record, is_owner_or_mod, make_file_link
from plugins.clone import mongo_db
from config import ADMINS, PUBLIC_FILE_STORE


def is_allowed_universal(client, user_id: int) -> bool:
    if PUBLIC_FILE_STORE:
        return True
    try:
        if int(user_id) in [int(x) for x in ADMINS if str(x).strip().lstrip("-").isdigit()]:
            return True
    except Exception:
        pass
    if is_owner_or_mod(client, user_id):
        return True
    return bot_record(client).get("mode") == "public"


async def universal_link_cmd(client, message):
    if not is_allowed_universal(client, message.from_user.id):
        return await message.reply("❌ Link generation is private. Only owner/moderators can use it.")

    replied = message.reply_to_message
    if not replied or not replied.media:
        return await message.reply("Reply to a video, audio or document and use <code>/universal_link</code>.")

    media = getattr(replied, replied.media.value, None)
    file_id = getattr(media, "file_id", None)
    if not file_id:
        return await message.reply("❌ Supported media: video, audio or document.")

    rec = bot_record(client)
    protected = bool(rec.get("protect_content", False)) or bool(rec.get("no_forward", False))
    username = (await client.get_me()).username
    link = make_file_link(username, file_id, protected)

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy Link 📋", url=f"https://t.me/share/url?url={link}"),
            InlineKeyboardButton("📢 SHARE URL 📢", url=f"https://t.me/share/url?url={link}")
        ]
    ])
    await message.reply(f"🔗 <b>Universal File Link:</b>\n{link}", reply_markup=markup, disable_web_page_preview=True)
    raise StopPropagation


def register(client, base_group=-104):
    private = filters.private
    client.add_handler(MessageHandler(universal_link_cmd, filters.command(["universal_link"]) & private), group=base_group)
    return client
