"""Shared auto-delete delivery helper for link-generated files.

This module is intentionally scoped to the link generator delivery handlers.
It does not change unrelated bot messages or buttons.
"""
import asyncio
import inspect

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


_TARGET_FUNCTIONS = {
    "batch_start",          # link_modules.custom_batch
    "batch_start_deliver",  # link_modules.channel_batch
    "special_link_start",   # link_modules.special_link
}


def _is_target_delivery_call():
    """Return True only when copy_message was called by a target link delivery."""
    frame = inspect.currentframe()
    try:
        frame = frame.f_back if frame else None
        while frame:
            fn = frame.f_code.co_name
            filename = frame.f_code.co_filename.replace("\\", "/")
            if fn in _TARGET_FUNCTIONS and "/link_modules/" in filename:
                return True
            frame = frame.f_back
    finally:
        del frame
    return False


def _build_auto_delete_markup(record):
    rows = []
    for row in record.get("auto_delete_buttons", []) or []:
        row_buttons = []
        if isinstance(row, dict) and "buttons" in row:
            buttons = row.get("buttons") or []
        elif isinstance(row, dict) and row.get("text"):
            buttons = [row]
        elif isinstance(row, list):
            buttons = row
        else:
            buttons = []

        for button in buttons:
            if not isinstance(button, dict):
                continue
            text = button.get("text")
            url = button.get("url")
            if text and url:
                row_buttons.append(InlineKeyboardButton(str(text), url=str(url)))
        if row_buttons:
            rows.append(row_buttons)
    return InlineKeyboardMarkup(rows) if rows else None


async def _send_auto_delete_notice(client, user_id, record, seconds):
    from clone_plugins.users_api import format_auto_delete_time

    time_str = format_auto_delete_time(seconds)
    mention = f"<a href='tg://user?id={int(user_id)}'>User</a>"
    try:
        user = await client.get_users(int(user_id))
        if user:
            mention = getattr(user, "mention", None) or getattr(user, "first_name", None) or mention
    except Exception:
        pass

    raw_text = record.get("auto_delete_text") or (
        "<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\n"
        "This Movie File/Video will be deleted in <b><u>{time}</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n"
        "<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
    )
    text = str(raw_text).replace("{time}", time_str).replace("{user_mention}", mention)
    markup = _build_auto_delete_markup(record)

    warning = None
    picture = record.get("auto_delete_pic")
    spoiler = bool(record.get("auto_delete_pic_spoiler", False))
    invert = bool(record.get("auto_delete_pic_invert_caption", False))

    if picture:
        try:
            warning = await client.send_photo(
                chat_id=int(user_id),
                photo=picture,
                caption=text,
                has_spoiler=spoiler,
                show_caption_above_media=invert,
                reply_markup=markup,
            )
        except Exception:
            try:
                warning = await client.send_photo(
                    chat_id=int(user_id),
                    photo=picture,
                    caption=text,
                    has_spoiler=spoiler,
                    reply_markup=markup,
                )
            except Exception:
                warning = None

    if warning is None:
        try:
            warning = await client.send_message(
                chat_id=int(user_id),
                text=text,
                reply_markup=markup,
            )
        except Exception:
            warning = None

    return warning


async def _schedule_delete(client, delivered, warning, seconds):
    await asyncio.sleep(seconds)
    try:
        await delivered.delete()
    except Exception:
        pass
    if warning:
        try:
            await warning.delete()
        except Exception:
            pass


def install_link_auto_delete(client):
    """Wrap only link-module copy_message deliveries with Auto Delete."""
    if getattr(client, "_ash_link_auto_delete_installed", False):
        return client

    original = client.copy_message

    async def wrapped_copy_message(*args, **kwargs):
        delivered = await original(*args, **kwargs)

        if not _is_target_delivery_call():
            return delivered

        try:
            chat_id = kwargs.get("chat_id")
            if chat_id is None and args:
                chat_id = args[0]
            if chat_id is None:
                return delivered

            from clone_plugins.commands import bot_record
            record = bot_record(client)
            if not record.get("auto_delete_enabled", False):
                return delivered

            seconds = int(record.get("auto_delete_time") or (int(record.get("auto_delete_minutes", 15)) * 60))
            seconds = max(1, seconds)
            warning = await _send_auto_delete_notice(client, int(chat_id), record, seconds)
            asyncio.create_task(_schedule_delete(client, delivered, warning, seconds))
        except Exception:
            # Never break file delivery because Auto Delete configuration failed.
            pass

        return delivered

    client.copy_message = wrapped_copy_message
    client._ash_link_auto_delete_installed = True
    return client
