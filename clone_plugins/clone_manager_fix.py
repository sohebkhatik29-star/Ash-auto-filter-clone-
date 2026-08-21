"""Focused clone-manager UI fixes.
Only changes the clone-management entry/menu and enforces a per-user 5-bot cap.
"""
import asyncio
import logging
import random
import re
from pyrogram import Client, filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMINS, BOT_USERNAME, PICS, UPDATE_CHANNEL, tg_link
from Script import script
from plugins import master_settings
from clone_plugins import master_manager
from clone_plugins.sessions import start_user_session, cancel_all_listeners

MAX_USER_CLONES = master_manager.MAX_USER_CLONES

manage_clones_markup = master_manager.manage_clones_markup
master_settings.manage_clones_markup = manage_clones_markup


def master_clone_hub_markup():
    """The only three actions shown when entering the master clone manager."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 MY CLONE BOT", callback_data="master_customize_clones")],
        [InlineKeyboardButton("➕ ADD CLONE BOT", callback_data="create_clone_prompt")],
        [InlineKeyboardButton("‹ BACK", callback_data="master_clone_manager_back")],
    ])


async def send_master_clone_hub(client, target):
    """Show the three-button clone manager without changing any other menu."""
    text = (
        "🤖 <b>MY CLONE BOT</b>\n\n"
        "Choose an option below to manage your clone bots."
    )
    msg = getattr(target, "message", None) or target
    try:
        await msg.edit_caption(caption=text, reply_markup=master_clone_hub_markup())
    except Exception:
        try:
            await msg.edit_text(text=text, reply_markup=master_clone_hub_markup())
        except Exception:
            await client.send_message(
                chat_id=getattr(target, "from_user", None).id if getattr(target, "from_user", None) else msg.chat.id,
                text=text,
                reply_markup=master_clone_hub_markup(),
            )


async def send_master_start_menu(client, query):
    """Return to the existing master start menu exactly as before."""
    me = client.me or (await client.get_me())
    buttons = [
        [
            InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"),
            InlineKeyboardButton("🤖 MY OWN BOT", callback_data="clone_my_bots"),
        ],
        [
            InlineKeyboardButton("💁 HELP", callback_data="help"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="about"),
        ],
        [
            InlineKeyboardButton(
                "📢 UPDATE CHANNEL",
                url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"),
            )
        ],
    ]
    caption = script.CLONE_START_TXT.format(query.from_user.mention, me.mention)
    if query.message.photo:
        return await query.message.edit_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    return await query.message.edit_text(
        caption,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Client.on_callback_query(filters.regex(r"^clone_my_bots$"))
async def clone_my_bots_entry(client, query):
    """
    This is the single entry point for MY OWN BOT.

    From a clone: open the master bot's clone manager.
    From the master: show the new three-button clone manager.
    """
    me = client.me or (await client.get_me())
    is_clone = bool(me and me.username and me.username.lower() != BOT_USERNAME.lower())

    if is_clone:
        try:
            await query.answer(
                url=f"https://t.me/{BOT_USERNAME}?start=my_clones"
            )
        except Exception:
            pass
        raise StopPropagation

    await query.answer()
    await send_master_clone_hub(client, query)
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^master_customize_clones$"))
async def master_customize_clones(client, query):
    """Open the user's clone list only after MY CLONE BOT is selected."""
    await query.answer()
    text = (
        "✨ <b>HERE ARE YOUR ACTIVE BOTS WITH POWERFUL CLONING AND CUSTOMIZATION</b>\n\n"
        "📲 <b>CLICK THE BUTTON BELOW TO OPEN YOUR CLONE BOT AND MODIFY ITS SETTINGS, WELCOME MESSAGE, AND FEATURES!</b>"
    )
    await master_manager.edit_or_reply(
        query,
        text,
        reply_markup=manage_clones_markup(
            query.from_user.id,
            back_cb="master_clone_manager_back",
            is_clone=False,
        ),
    )
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^master_clone_manager_back$"))
async def master_clone_manager_back(client, query):
    """Back from the clone manager returns to the existing start menu."""
    await query.answer()
    await send_master_start_menu(client, query)
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^clone_limit$"))
async def clone_limit(client, query):
    await query.answer("❌ You can create maximum 5 clone bots.", show_alert=True)
    raise StopPropagation


async def create_clone_prompt_no_listener(client, query):
    """Start master clone creation without Client.listen().

    The forwarded BotFather message is handled by master_clone_forward.py.
    Client.listen() was racing that handler and consuming the forwarded message,
    which is why the user saw no response after forwarding BotFather's message.
    """
    user_id = int(query.from_user.id)
    m = master_manager.db()

    if m is not None:
        current_count = m.bots.count_documents({"user_id": user_id})
        if current_count >= MAX_USER_CLONES:
            await query.answer("❌ You can create maximum 5 clone bots.", show_alert=True)
            raise StopPropagation

    await query.answer()
    cancel_all_listeners(client, query.message.chat.id, user_id)
    sess_token = start_user_session(user_id, "create_clone")

    await client.send_message(
        chat_id=user_id,
        text=(
            "🤖 <b>CREATE CLONE BOT:</b>\n\n"
            "1) Create a bot using @BotFather.\n"
            "2) Forward the BotFather message containing the bot token here.\n"
            "3) I will automatically create your clone.\n\n"
            "<i>Send /cancel to abort.</i>"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ CANCEL", callback_data="my_clones")]
        ]),
    )

    # Keep a session marker only. Do NOT start Client.listen(); the dedicated
    # forwarded-message handler must receive the BotFather message.
    _ = sess_token
    raise StopPropagation


@Client.on_callback_query(filters.regex(r"^create_clone_prompt$"))
async def create_clone_prompt(client, query):
    return await create_clone_prompt_no_listener(client, query)


@Client.on_message(filters.command("start") & filters.private)
async def clone_only_start(client, message):
    """Clone-only /start menu. Other commands and buttons stay untouched."""
    if len(message.command) != 1:
        return
    m = master_manager.db()
    if m is None:
        return
    rec = m.bots.find_one({"bot_id": client.me.id})
    if not rec:
        return
    me = await client.get_me()
    buttons = [
        [
            InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"),
            InlineKeyboardButton(
                "🤖 MY OWN BOT",
                callback_data="clone_my_bots",
            ),
        ],
        [
            InlineKeyboardButton("💁 HELP", callback_data="help"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="about"),
        ],
        [
            InlineKeyboardButton(
                "📢 UPDATE CHANNEL",
                url=tg_link(UPDATE_CHANNEL, "MoviesGroupG3"),
            )
        ],
    ]
    caption = script.CLONE_START_TXT.format(
        message.from_user.mention,
        me.mention,
    )
    start_photo = rec.get("start_pic") or random.choice(PICS)
    try:
        await message.reply_photo(
            photo=start_photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except Exception:
        await message.reply(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    raise StopPropagation


@Client.on_message(filters.command("start") & filters.private)
async def master_my_clones_start(client, message):
    """Deep-link target used by MY OWN BOT inside a clone."""
    if len(message.command) != 2 or message.command[1].lower() != "my_clones":
        return
    m = master_manager.db()
    if m is None or m.bots.find_one({"bot_id": client.me.id}):
        return
    await send_master_clone_hub(client, message)
    raise StopPropagation


def register_clone_manager_navigation(client, master=False):
    """Explicitly register only the clone-manager handlers on the real client instance.

    The decorator-based handlers above are used by the master plugin loader, but
    dynamically-created clone clients are registered manually. This explicit
    registration keeps this change limited to the clone-manager navigation.
    """
    if master:
        client.add_handler(
            MessageHandler(
                master_my_clones_start,
                filters.command("start") & filters.private,
            ),
            group=-100,
        )
        client.add_handler(
            CallbackQueryHandler(
                clone_my_bots_entry,
                filters.regex(r"^clone_my_bots$"),
            ),
            group=-100,
        )
        client.add_handler(
            CallbackQueryHandler(
                master_customize_clones,
                filters.regex(r"^master_customize_clones$"),
            ),
            group=-100,
        )
        # IMPORTANT: this must run before the old master_manager callback
        # handler. It starts only the session marker; no Client.listen() task
        # is created, so forwarded BotFather messages reach the dedicated
        # master_clone_forward handler.
        client.add_handler(
            CallbackQueryHandler(
                create_clone_prompt_no_listener,
                filters.regex(r"^create_clone_prompt$"),
            ),
            group=-101,
        )
        client.add_handler(
            CallbackQueryHandler(
                create_clone_prompt,
                filters.regex(r"^create_clone_prompt$"),
            ),
            group=-100,
        )
        client.add_handler(
            CallbackQueryHandler(
                master_clone_manager_back,
                filters.regex(r"^master_clone_manager_back$"),
            ),
            group=-100,
        )
    else:
        client.add_handler(
            CallbackQueryHandler(
                clone_my_bots_entry,
                filters.regex(r"^clone_my_bots$"),
            ),
            group=-100,
        )
