"""Helper functions for file-link commands."""
import base64
from pyrogram.types import Message


def encode_payload(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def extract_file_id(message: Message):
    media = message.media
    if not media:
        return None
    obj = getattr(message, media.value, None)
    return getattr(obj, "file_id", None)

