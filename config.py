import re
import os
from os import environ
from Script import script

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# Bot Information
API_ID = int(environ.get("API_ID", "0"))
API_HASH = environ.get("API_HASH", "")
BOT_TOKEN = environ.get("BOT_TOKEN", "")

PICS = (environ.get('PICS', 'https://graph.org/file/ce1723991756e48c35aa1.jpg')).split()
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()]
BOT_USERNAME = environ.get("BOT_USERNAME", "Ash_files_or_clone_mangar_bot")
PORT = environ.get("PORT", "8080")

# Clone Info
CLONE_MODE = is_enabled(environ.get('CLONE_MODE', 'False'), False)
CLONE_DB_URI = environ.get("CLONE_DB_URI", "")
CDB_NAME = environ.get("CDB_NAME", "ash_clone_db")

# Database Information
DB_URI = environ.get("DB_URI", "")
DB_NAME = environ.get("DB_NAME", "ash_file_store")

# Auto Delete Information
AUTO_DELETE_MODE = is_enabled(environ.get('AUTO_DELETE_MODE', 'True'), True)
AUTO_DELETE = int(environ.get("AUTO_DELETE", "30"))
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", "1800"))

# Channel Information
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "0"))
SUPPORT_GROUP = environ.get("SUPPORT_GROUP", "ash_movie_j")
UPDATE_CHANNEL = environ.get("UPDATE_CHANNEL", environ.get("UPDATES_CHANNEL", "MoviesGroupG3"))

def tg_link(name_or_url, default=""):
    val = (name_or_url or default or "").strip()
    if not val:
        return "https://t.me/"
    if val.startswith("https://") or val.startswith("http://"):
        return val
    return f"https://t.me/{val.lstrip('@')}"

# File Caption Information
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

PUBLIC_FILE_STORE = is_enabled(environ.get('PUBLIC_FILE_STORE', "True"), True)

# Verify Info
VERIFY_MODE = is_enabled(environ.get('VERIFY_MODE', 'False'), False)
SHORTLINK_URL = environ.get("SHORTLINK_URL", "")
SHORTLINK_API = environ.get("SHORTLINK_API", "")
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "")

# Website Info
WEBSITE_URL_MODE = is_enabled(environ.get('WEBSITE_URL_MODE', 'False'), False)
WEBSITE_URL = environ.get("WEBSITE_URL", "")

# File Stream Config
STREAM_MODE = is_enabled(environ.get('STREAM_MODE', 'True'), True)
MULTI_CLIENT = False
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))

if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False

URL = environ.get("URL", "")
