from pyrogram import filters, StopPropagation
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMINS, SUPPORT_GROUP, UPDATE_CHANNEL, BOT_USERNAME, PICS, tg_link
from Script import script
from clone_plugins.master_manager import docs_for, list_markup, manage_clone, clone_manage_action, clone_delete, get_bot
from plugins.users_api import get_user, update_user_info
import random


def master_settings_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("MY CLONE BOT 🤖", callback_data="my_clone")],
        [InlineKeyboardButton("GOOGLE BACKUP 📁", callback_data="master_google_backup")],
        [InlineKeyboardButton("LINK SHORTENER 📎", callback_data="link_shortener")],
        [InlineKeyboardButton("CUSTOM CAPTION 🖌", callback_data="custom_caption")],
        [InlineKeyboardButton("CUSTOM BUTTON ➕", callback_data="custom_button")],
        [InlineKeyboardButton("PROTECT CONTENT ☂️", callback_data="protect_menu")],
        [InlineKeyboardButton("START PHOTO 🖼️", callback_data="start_photo_menu")],
        [InlineKeyboardButton("‹ BACK", callback_data="settings_back")],
    ])


async def send_settings_menu(client, message):
    text = "⚙️ <b>Settings</b>\n\nCustomize your settings as your need"
    if hasattr(message, "reply_text"):
        return await message.reply_text(
            text,
            reply_markup=master_settings_markup(),
        )
    return await message.reply(
        text,
        reply_markup=master_settings_markup(),
    )


async def settings(client, message):
    await send_settings_menu(client, message)
    raise StopPropagation


async def callbacks(client, query):
    data = query.data or ""

    if data in ("settings", "master_settings"):
        text = "⚙️ <b>Settings</b>\n\nCustomize your settings as your need"
        await query.message.edit_text(text, reply_markup=master_settings_markup())
        await query.answer()
        raise StopPropagation

    if data in ("my_clone", "my_clones"):
        docs = docs_for(query.from_user.id)
        text = (
            "✨ <b>Manage Clone's</b>\n\n"
            "You can now manage and create your very own identical clone bot, "
            "mirroring all my awesome features, using the given buttons."
        )
        if not docs:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 CREATE NEW CLONE", callback_data="clone")],
                [InlineKeyboardButton("‹ back", callback_data="master_settings")]
            ])
            await query.message.edit_text(text, reply_markup=markup)
            await query.answer()
            raise StopPropagation

        rows = []
        for d in docs:
            bid = int(d["bot_id"])
            name = d.get("name") or d.get("username") or str(bid)
            rows.append([InlineKeyboardButton(f"{name[:32]}", callback_data=f"manage_clone:{bid}")])
        rows.append([InlineKeyboardButton("‹ back", callback_data="master_settings")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))
        await query.answer()
        raise StopPropagation

    if data in ("google_backup", "master_google_backup"):
        text = (
            "<b>Clone Backup</b>\n\n"
            "You can connect a google account to retrieve ownership and data of clones in this tg account, "
            "if this account is deleted or you loose access to it, use /recover to restore them."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Connect With Google", callback_data="google_connect")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "google_connect":
        await query.answer("Google Drive backup is stored securely in MongoDB database.", show_alert=True)
        raise StopPropagation

    if data == "link_shortener":
        user = await get_user(query.from_user.id)
        site = user.get("base_site") or "Not set"
        api = user.get("shortener_api") or "Not set"
        text = (
            "<b>Link Shortener</b>\n"
            f"- Shortener: {site}\n"
            f"- Shortener Api: {api}\n\n"
            "You can now use the /shortener command to shorten any links."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Delete shortener", callback_data="delete_shortener")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "delete_shortener":
        await update_user_info(query.from_user.id, {"base_site": None, "shortener_api": None})
        await query.answer("Shortener deleted.", show_alert=True)
        text = (
            "<b>Link Shortener</b>\n"
            "- Shortener: Not set\n"
            "- Shortener Api: Not set\n\n"
            "You can now use the /shortener command to shorten any links."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Delete shortener", callback_data="delete_shortener")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        raise StopPropagation

    if data == "custom_caption":
        user = await get_user(query.from_user.id)
        text = (
            "<b>Custom Caption:</b>\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        cap = user.get("custom_caption")
        if cap:
            text += f"\n\n<b>Current:</b> <code>{cap}</code>"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="caption_edit"),
                InlineKeyboardButton("See", callback_data="caption_see"),
                InlineKeyboardButton("Delete", callback_data="caption_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "caption_see":
        user = await get_user(query.from_user.id)
        cap = user.get("custom_caption") or "Default caption"
        await query.answer(f"Caption:\n{cap}", show_alert=True)
        raise StopPropagation

    if data == "caption_delete":
        await update_user_info(query.from_user.id, {"custom_caption": None})
        await query.answer("Custom caption deleted.", show_alert=True)
        text = (
            "<b>Custom Caption:</b>\n"
            "You can add a custom caption to your media messages instead of its original caption\n\n"
            "<b>Fillings:</b>\n"
            "• {file_name} : File Name\n"
            "• {file_size} : File Size\n"
            "• {caption} : Orginal Caption"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="caption_edit"),
                InlineKeyboardButton("See", callback_data="caption_see"),
                InlineKeyboardButton("Delete", callback_data="caption_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        raise StopPropagation

    if data == "caption_edit":
        await query.answer("Send /caption <Your Text> to update caption.", show_alert=True)
        raise StopPropagation

    if data == "custom_button":
        text = "<b>Custom Button:</b>\nYou can add a custom button to your message"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕", callback_data="button_add")],
            [InlineKeyboardButton("‹ back", callback_data="master_settings"), InlineKeyboardButton("Delete", callback_data="button_delete")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "button_add":
        await query.answer("Send /button <Button Text> - <URL> to set custom button.", show_alert=True)
        raise StopPropagation

    if data == "button_delete":
        await update_user_info(query.from_user.id, {"custom_buttons": []})
        await query.answer("Custom button deleted.", show_alert=True)
        raise StopPropagation

    if data == "protect_menu":
        user = await get_user(query.from_user.id)
        is_on = bool(user.get("protect_content", False))
        status_str = "ENABLED ✅" if is_on else "DISABLED ❌"
        text = (
            "<b>Protect Content</b>\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's:</b>\n"
            "1) Enable: Forwarding is blocked. Once you create a link with this mode, the restriction remains even if you later disabled this feature.\n"
            "2) Disable: Forwarding restrictions depend on whether the \"no forward\" feature is currently enabled in the bot. If enabled, no forward is restricted. This applies to all links, including those created before; if disabled, forwarding is allowed.\n\n"
            f"- status: {status_str}"
        )
        btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle_off") if is_on else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle_on")
        markup = InlineKeyboardMarkup([
            [btn],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data in ("protect_toggle_on", "protect_toggle_off"):
        val = (data == "protect_toggle_on")
        await update_user_info(query.from_user.id, {"protect_content": val})
        status_str = "ENABLED ✅" if val else "DISABLED ❌"
        text = (
            "<b>Protect Content</b>\n"
            "Restrict other users from forwarding contents from your shareable link.\n\n"
            "<b>Available Mode's:</b>\n"
            "1) Enable: Forwarding is blocked. Once you create a link with this mode, the restriction remains even if you later disabled this feature.\n"
            "2) Disable: Forwarding restrictions depend on whether the \"no forward\" feature is currently enabled in the bot. If enabled, no forward is restricted. This applies to all links, including those created before; if disabled, forwarding is allowed.\n\n"
            f"- status: {status_str}"
        )
        btn = InlineKeyboardButton("Disable ❌", callback_data="protect_toggle_off") if val else InlineKeyboardButton("Enable ✅", callback_data="protect_toggle_on")
        markup = InlineKeyboardMarkup([
            [btn],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "start_photo_menu":
        user = await get_user(query.from_user.id)
        has_pic = bool(user.get("start_pic"))
        status_str = "CUSTOM PHOTO SET ✅" if has_pic else "DEFAULT PHOTO 🖼️"
        text = (
            "<b>Start Message Photo:</b>\n"
            "You can set a custom photo/banner that appears on /start command.\n\n"
            f"• <b>Status:</b> {status_str}\n\n"
            "• <b>Set/Edit:</b> Send <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>\n"
            "• <b>See:</b> View your current start photo\n"
            "• <b>Delete:</b> Reset to default photo"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="start_pic_edit"),
                InlineKeyboardButton("See", callback_data="start_pic_see"),
                InlineKeyboardButton("Delete", callback_data="start_pic_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        raise StopPropagation

    if data == "start_pic_edit":
        await query.answer("Send /set_pic <Image_URL> or reply to a photo with /set_pic", show_alert=True)
        raise StopPropagation

    if data == "start_pic_see":
        user = await get_user(query.from_user.id)
        pic = user.get("start_pic")
        if pic:
            try:
                await client.send_photo(chat_id=query.from_user.id, photo=pic, caption="🖼️ <b>Your Custom Start Photo</b>")
                await query.answer()
            except Exception:
                await query.answer(f"Photo URL:\n{pic}", show_alert=True)
        else:
            await query.answer("You are currently using the default start photo.", show_alert=True)
        raise StopPropagation

    if data == "start_pic_delete":
        await update_user_info(query.from_user.id, {"start_pic": None})
        await query.answer("Start photo reset to default.", show_alert=True)
        text = (
            "<b>Start Message Photo:</b>\n"
            "You can set a custom photo/banner that appears on /start command.\n\n"
            "• <b>Status:</b> DEFAULT PHOTO 🖼️\n\n"
            "• <b>Set/Edit:</b> Send <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>\n"
            "• <b>See:</b> View your current start photo\n"
            "• <b>Delete:</b> Reset to default photo"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Edit", callback_data="start_pic_edit"),
                InlineKeyboardButton("See", callback_data="start_pic_see"),
                InlineKeyboardButton("Delete", callback_data="start_pic_delete")
            ],
            [InlineKeyboardButton("‹ back", callback_data="master_settings")]
        ])
        await query.message.edit_text(text, reply_markup=markup)
        raise StopPropagation

    if data == "settings_back":
        buttons = [[
            InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://www.youtube.com/@tech_as_0')
        ],[
            InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url=tg_link(SUPPORT_GROUP, 'ash_movie_j')),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url=tg_link(UPDATE_CHANNEL, 'MoviesGroupG3'))
        ],[
            InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ],[
            InlineKeyboardButton('🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='settings')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me or (await client.get_me())
        caption = script.START_TXT.format(query.from_user.mention, me.mention)
        if query.message.photo:
            await query.message.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            await query.message.edit_text(text=caption, reply_markup=reply_markup)
        await query.answer()
        raise StopPropagation

    if data.startswith("manage_clone:"):
        await manage_clone(client, query)
        raise StopPropagation
    if data.startswith("cm:"):
        await clone_manage_action(client, query)
        raise StopPropagation
    if data.startswith("cmdelete:"):
        await clone_delete(client, query)
        raise StopPropagation


async def set_pic_cmd(client, message):
    user_id = message.from_user.id
    pic_url = None
    if message.reply_to_message and message.reply_to_message.photo:
        pic_url = message.reply_to_message.photo.file_id
    elif len(message.command) > 1:
        pic_url = message.command[1].strip()
    if not pic_url:
        return await message.reply_text("❌ <b>Usage:</b>\nSend <code>/set_pic https://example.com/image.jpg</code> or reply to a photo with <code>/set_pic</code>")
    await update_user_info(user_id, {"start_pic": pic_url})
    await message.reply_text("✅ <b>Custom start photo saved successfully!</b>")


async def del_pic_cmd(client, message):
    user_id = message.from_user.id
    await update_user_info(user_id, {"start_pic": None})
    await message.reply_text("✅ <b>Start photo reset to default.</b>")


async def get_pic_cmd(client, message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    pic = user.get("start_pic")
    if pic:
        try:
            return await message.reply_photo(photo=pic, caption="🖼️ <b>Your Custom Start Photo</b>")
        except Exception:
            return await message.reply_text(f"🖼️ <b>Your Custom Start Photo URL:</b>\n{pic}")
    await message.reply_text("ℹ️ <b>You are using default start photo.</b>")


def register(client):
    client.add_handler(MessageHandler(settings, filters.command("settings") & filters.private), group=-1)
    client.add_handler(MessageHandler(set_pic_cmd, filters.command(["set_pic", "setpic"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(del_pic_cmd, filters.command(["del_pic", "delpic"]) & filters.private), group=-1)
    client.add_handler(MessageHandler(get_pic_cmd, filters.command(["get_pic", "getpic"]) & filters.private), group=-1)
    client.add_handler(
        CallbackQueryHandler(
            callbacks,
            filters.regex(r"^(settings|master_settings|settings_back|my_clone|my_clones|google_backup|master_google_backup|google_connect|link_shortener|delete_shortener|custom_caption|caption_see|caption_delete|caption_edit|custom_button|button_add|button_delete|protect_menu|protect_toggle_on|protect_toggle_off|start_photo_menu|start_pic_edit|start_pic_see|start_pic_delete|manage_clone:\d+|cm:\d+:[a-z_]+|cmdelete:\d+)$"),
        ),
        group=-1,
    )
