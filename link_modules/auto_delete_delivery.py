"""Shared auto-delete delivery and link-shortening helpers for link generators.

Auto Delete remains scoped to the link generator delivery handlers.
Link shortening is separately scoped to the five requested link-generation flows:
/getlink, /batch, /custom_batch, /special_link and /universal_link.
"""
import asyncio
import inspect
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


_TARGET_FUNCTIONS = {
    "batch_start",
    "batch_start_deliver",
    "special_link_start",
}

_SHORTENER_FUNCTIONS = {
    "capture_single",
    "start_batch",
    "_generate",
    "special_link_callbacks",
    "universal_link_cmd",
}

_URL_RE = re.compile(r"https?://[^\s<>\"']+")


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


def _is_target_shortener_call():
    """Return True only while one of the five requested link generators is creating its link."""
    frame = inspect.currentframe()
    try:
        frame = frame.f_back if frame else None
        while frame:
            fn = frame.f_code.co_name
            filename = frame.f_code.co_filename.replace("\\", "/")
            if fn in _SHORTENER_FUNCTIONS and "/link_modules/" in filename:
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


async def schedule_auto_delete(client, user_id, delivered_messages, seconds):
    from clone_plugins.commands import bot_record
    record = bot_record(client)
    warning = await _send_auto_delete_notice(client, int(user_id), record, seconds)
    
    async def _delete_all():
        await asyncio.sleep(seconds)
        for msg in delivered_messages:
            try:
                await msg.delete()
            except Exception:
                pass
        if warning:
            try:
                await warning.delete()
            except Exception:
                pass
    
    asyncio.create_task(_delete_all())


async def _shorten_generated_link(client, link):
    """Shorten one generated link using the clone's Link Shortener settings."""
    if not link or not isinstance(link, str) or not link.startswith(("http://", "https://")):
        return link

    try:
        from clone_plugins.commands import bot_record
        from clone_plugins.users_api import get_short_link

        record = bot_record(client) or {}
        # Only shorten if shortener is actively enabled (ON)
        if not bool(record.get("shortener_enabled", False)):
            return link

        api_key = record.get("shortener_api")
        site = record.get("base_site") or record.get("shortener_site")
        if not api_key or not site:
            return link

        user = {
            "shortener_api": api_key,
            "base_site": site,
            "shortener_site": site,
        }
        shortened = await get_short_link(user, link)
        if shortened and isinstance(shortened, str) and shortened.startswith(("http://", "https://")):
            return shortened.strip()
    except Exception:
        pass
    return link


def _extract_main_url(text):
    if not text:
        return None
    match = _URL_RE.search(str(text))
    if not match:
        return None
    return match.group(0).rstrip(".,!?)\\\"]")


def _replace_main_url(text, original, shortened):
    if not text or not original or not shortened:
        return text
    return str(text).replace(original, shortened)


def _shorten_markup_urls(markup, original, shortened):
    """Preserve all existing buttons, changing only the generated-link URL."""
    if not markup or not getattr(markup, "inline_keyboard", None):
        return markup

    new_rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for button in row:
            button_url = getattr(button, "url", None)
            if not button_url or not original:
                new_row.append(button)
                continue

            new_url = button_url
            if button_url == original:
                new_url = shortened
            elif "t.me/share/url" in button_url:
                try:
                    parsed = urlsplit(button_url)
                    params = parse_qs(parsed.query, keep_blank_values=True)
                    values = params.get("url") or []
                    if values and values[0] == original:
                        params["url"] = [shortened]
                        query = urlencode(params, doseq=True)
                        new_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
                except Exception:
                    pass

            if new_url == button_url:
                new_row.append(button)
            else:
                new_row.append(InlineKeyboardButton(button.text, url=new_url))
        new_rows.append(new_row)

    return InlineKeyboardMarkup(new_rows)


async def _prepare_shortened_output(client, text, reply_markup):
    if not _is_target_shortener_call():
        return text, reply_markup

    original = _extract_main_url(text)
    if not original:
        return text, reply_markup

    shortened = await _shorten_generated_link(client, original)
    if not shortened or shortened == original:
        return text, reply_markup

    return (
        _replace_main_url(text, original, shortened),
        _shorten_markup_urls(reply_markup, original, shortened),
    )


def install_link_auto_delete(client):
    """Install narrowly scoped Link Shortener wrappers."""
    if getattr(client, "_ash_link_auto_delete_installed", False):
        return client

    original_send_message = client.send_message
    original_edit_message_text = client.edit_message_text

    async def wrapped_send_message(*args, **kwargs):
        if _is_target_shortener_call():
            text = kwargs.get("text")
            reply_markup = kwargs.get("reply_markup")
            if text is None and len(args) >= 2:
                text = args[1]
            new_text, new_markup = await _prepare_shortened_output(client, text, reply_markup)
            if "text" in kwargs:
                kwargs["text"] = new_text
            elif len(args) >= 2:
                args = list(args)
                args[1] = new_text
                args = tuple(args)
            if "reply_markup" in kwargs:
                kwargs["reply_markup"] = new_markup
            elif new_markup is not None:
                kwargs["reply_markup"] = new_markup
        return await original_send_message(*args, **kwargs)

    async def wrapped_edit_message_text(*args, **kwargs):
        if _is_target_shortener_call():
            text = kwargs.get("text")
            reply_markup = kwargs.get("reply_markup")
            if text is None and len(args) >= 3:
                text = args[2]
            new_text, new_markup = await _prepare_shortened_output(client, text, reply_markup)
            if "text" in kwargs:
                kwargs["text"] = new_text
            elif len(args) >= 3:
                args = list(args)
                args[2] = new_text
                args = tuple(args)
            if "reply_markup" in kwargs:
                kwargs["reply_markup"] = new_markup
            elif new_markup is not None:
                kwargs["reply_markup"] = new_markup
        return await original_edit_message_text(*args, **kwargs)

    client.send_message = wrapped_send_message
    client.edit_message_text = wrapped_edit_message_text
    client._ash_link_auto_delete_installed = True
    return client
