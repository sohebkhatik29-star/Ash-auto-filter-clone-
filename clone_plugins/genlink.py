# ASH FILE STORE & CLONE MANAGER
# Telegram: @movies_1780

import base64
from pyrogram import Client, filters, enums
from clone_plugins.users_api import get_user, get_short_link


async def _make_link(client, message):
    replied = message.reply_to_message
    if not replied:
        return await message.reply("Reply to a video, audio or document message.")

    media_type = replied.media
    if media_type not in [
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.AUDIO,
        enums.MessageMediaType.DOCUMENT,
    ]:
        return await message.reply("❌ Supported media: video, audio or document.")

    media = getattr(replied, media_type.value, None)
    file_id = getattr(media, "file_id", None)
    if not file_id:
        return await message.reply("❌ I couldn't read the file ID.")

    # The start handler understands file_<file_id> payloads.
    payload = "file_" + file_id
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    bot_username = (await client.get_me()).username
    share_link = f"https://t.me/{bot_username}?start={encoded}"

    user = await get_user(message.from_user.id)
    api_key = user.get("shortener_api")
    base_site = user.get("base_site")

    if api_key and base_site:
        short_link = await get_short_link(user, share_link)
        if short_link != share_link:
            return await message.reply(
                f"<b>🔗 Your Short Link:</b>\n\n{short_link}\n\n"
                f"<b>🔗 Original Link:</b>\n{share_link}"
            )

    await message.reply(f"<b>🔗 Your File Link:</b>\n\n{share_link}")


@Client.on_message(filters.command(["link", "genlink"]) & filters.private)
async def gen_link_s(client, message):
    await _make_link(client, message)


@Client.on_message(filters.command("batch") & filters.private)
async def batch_link(client, message):
    """Create a batch from a replied-to media message and an optional count.

    Usage: reply to the first file and send /batch N. Telegram message IDs are
    consecutive, so this validates the requested range before creating links.
    """
    replied = message.reply_to_message
    if not replied:
        return await message.reply("Reply to the first file and use <code>/batch N</code>.")

    try:
        count = int(message.command[1]) if len(message.command) > 1 else 1
        if count < 1 or count > 20:
            raise ValueError
    except ValueError:
        return await message.reply("Usage: <code>/batch 5</code> (1-20 files)")

    user = await get_user(message.from_user.id)
    bot_username = (await client.get_me()).username
    links = []

    for msg_id in range(replied.id, replied.id + count):
        try:
            msg = await client.get_messages(replied.chat.id, msg_id)
            if not msg or msg.empty:
                continue
            media_type = msg.media
            if media_type not in [
                enums.MessageMediaType.VIDEO,
                enums.MessageMediaType.AUDIO,
                enums.MessageMediaType.DOCUMENT,
            ]:
                continue
            media = getattr(msg, media_type.value, None)
            file_id = getattr(media, "file_id", None)
            if not file_id:
                continue
            payload = base64.urlsafe_b64encode(
                ("file_" + file_id).encode()
            ).decode().rstrip("=")
            links.append(f"https://t.me/{bot_username}?start={payload}")
        except Exception:
            continue

    if not links:
        return await message.reply("❌ No supported files were found in that range.")

    text = "<b>📦 Batch Links</b>\n\n" + "\n".join(
        f"{i}. {link}" for i, link in enumerate(links, 1)
    )
    await message.reply(text)
