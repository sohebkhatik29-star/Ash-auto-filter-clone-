"""Basic working file-link commands for the master bot."""
import base64
from pyrogram import Client, filters
from pyrogram.types import Message


def encode_payload(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def extract_file_id(message: Message):
    media = message.media
    if not media:
        return None
    obj = getattr(message, media.value, None)
    return getattr(obj, "file_id", None)


@Client.on_message(filters.command(["link", "genlink"]) & filters.private)
async def make_single_link(client, message):
    target = message.reply_to_message
    if not target:
        return await message.reply_text("Reply to a document/video/audio/photo and send /link")
    file_id = extract_file_id(target)
    if not file_id:
        return await message.reply_text("Please reply to a supported media/file message.")
    bot = await client.get_me()
    payload = encode_payload(f"file_{file_id}")
    await message.reply_text(f"<b>Your file link:</b>\nhttps://t.me/{bot.username}?start={payload}")


@Client.on_message(filters.command("batch") & filters.private)
async def batch_help(client, message):
    await message.reply_text(
        "<b>Batch link</b>\nReply to a supported file and use /link for a single-file link. "
        "Multi-message batch generation will be enabled after the file-store channel is configured."
    )
