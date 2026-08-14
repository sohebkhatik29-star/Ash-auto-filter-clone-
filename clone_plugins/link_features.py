"""Working file-link commands for every cloned bot.

Commands:
/link, /genlink, /batch
A link is a Telegram deep-link to the same clone bot.  The payload contains
only Telegram file/message IDs, so no bot token or database credential is
exposed in the URL.
"""
import base64
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from plugins.clone import mongo_db


def encode_payload(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_payload(value: str) -> str:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()


def extract_file_id(message: Message):
    media = message.media
    if not media:
        return None
    obj = getattr(message, media.value, None)
    return getattr(obj, "file_id", None)


async def make_link(client, owner_id: int, file_id: str, prefix: str = "file"):
    bot = await client.get_me()
    payload = encode_payload(f"{prefix}_{file_id}")
    return f"https://t.me/{bot.username}?start={payload}"


@Client.on_message(filters.command(["link", "genlink"]) & filters.private)
async def make_single_link(client, message):
    target = message.reply_to_message
    if not target:
        return await message.reply_text("Reply to a document/video/audio/photo and send /link")
    file_id = extract_file_id(target)
    if not file_id:
        return await message.reply_text("Please reply to a supported media/file message.")
    link = await make_link(client, message.from_user.id, file_id)
    await message.reply_text(f"<b>Your file link:</b>\n{link}")

