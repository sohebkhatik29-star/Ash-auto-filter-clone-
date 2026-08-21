"""Focused clone-manager UI fixes and helper exports.
Does NOT register duplicate global handlers.
"""
from config import ADMINS, BOT_USERNAME, PICS, UPDATE_CHANNEL, tg_link
from plugins import master_settings
from clone_plugins import master_manager

MAX_USER_CLONES = master_manager.MAX_USER_CLONES

manage_clones_markup = master_manager.manage_clones_markup
master_settings.manage_clones_markup = manage_clones_markup
