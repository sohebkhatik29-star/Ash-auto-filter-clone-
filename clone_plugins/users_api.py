# © Telegram : @movies_1780 , GitHub : @VJBots

import aiohttp
import time
import re
import uuid
from plugins.clone import mongo_db

def parse_time_string(val: str) -> int:
    val = (val or "").strip().lower()
    match = re.match(r"^(\d+)\s*([a-zA-Z]+)?$", val)
    if not match:
        digits = "".join(filter(str.isdigit, val))
        if digits:
            return max(1, int(digits))
        return 60
    num = int(match.group(1))
    unit = (match.group(2) or "m").lower()
    if unit.startswith("m") and not unit.startswith("mo"):
        return max(1, num)
    elif unit.startswith("h"):
        return max(1, num * 60)
    elif unit.startswith("d"):
        return max(1, num * 1440)
    elif unit.startswith("w"):
        return max(1, num * 1440 * 7)
    elif unit.startswith("mo"):
        return max(1, num * 1440 * 30)
    elif unit.startswith("y"):
        return max(1, num * 1440 * 365)
    return max(1, num)


def format_time_minutes(mins: int) -> str:
    mins = max(1, int(mins))
    if mins < 60:
        return f"{mins} Minutes"
    elif mins % 1440 == 0:
        d = mins // 1440
        return f"{d} Day" if d == 1 else f"{d} Days"
    elif mins % 60 == 0:
        h = mins // 60
        return f"{h} Hour" if h == 1 else f"{h} Hours"
    else:
        h = mins // 60
        m = mins % 60
        return f"{h}h {m}m"


def is_user_premium(user_id: int, source_doc: dict) -> bool:
    if not source_doc or not source_doc.get("premium_is_on", False):
        return False
    user_id = int(user_id)
    prem_users = source_doc.get("premium_users", [])
    now = int(time.time())
    for pu in prem_users:
        if int(pu.get("user_id", 0)) == user_id:
            if int(pu.get("expires_at", 0)) > now:
                return True
    return False


def check_user_verified(user_id: int, bot_id=0) -> bool:
    if mongo_db is None:
        return False
    now = int(time.time())
    rec = mongo_db.user_verifications.find_one({
        "user_id": int(user_id),
        "bot_id": int(bot_id),
        "expires_at": {"$gt": now}
    })
    return bool(rec)


def set_user_verified(user_id: int, bot_id=0, duration_minutes=480):
    if mongo_db is None:
        return
    now = int(time.time())
    expires = now + max(60, int(duration_minutes) * 60)
    mongo_db.user_verifications.update_one(
        {"user_id": int(user_id), "bot_id": int(bot_id)},
        {"$set": {"verified_at": now, "expires_at": expires}},
        upsert=True
    )


def create_verify_token(user_id: int, bot_id=0, payload="") -> str:
    token = uuid.uuid4().hex[:10]
    if mongo_db is not None:
        mongo_db.verify_tokens.update_one(
            {"token": token},
            {"$set": {
                "token": token,
                "user_id": int(user_id),
                "bot_id": int(bot_id),
                "payload": payload,
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 3600
            }},
            upsert=True
        )
    return token


def consume_verify_token(token: str, user_id: int, bot_id=0):
    if mongo_db is None:
        return None
    rec = mongo_db.verify_tokens.find_one({"token": token, "user_id": int(user_id), "bot_id": int(bot_id)})
    if not rec:
        return None
    mongo_db.verify_tokens.delete_one({"_id": rec["_id"]})
    if int(rec.get("expires_at", 0)) < int(time.time()):
        return None
    return rec.get("payload", "")


async def get_short_link(user, link):
    if not user:
        return link
    api_key = user.get("shortener_api")
    base_site = (user.get("base_site") or "").strip().rstrip("/")
    if not api_key or not base_site:
        return link
    
    clean_site = base_site.replace("https://", "").replace("http://", "").split("/")[0].strip()
    if not clean_site:
        return link

    # Universal shortener request handler
    urls_to_try = []
    if "shareus" in clean_site.lower():
        urls_to_try.append((f"https://api.shareus.io/easy_api", {"key": api_key, "link": link}))
        urls_to_try.append((f"https://{clean_site}/api", {"api": api_key, "url": link}))
    elif "tinyurl.com" in clean_site.lower():
        urls_to_try.append((f"https://tinyurl.com/api-create.php", {"url": link}))
    elif "bitly" in clean_site.lower():
        urls_to_try.append((f"https://{clean_site}/api", {"api": api_key, "url": link}))
    else:
        urls_to_try.append((f"https://{clean_site}/api", {"api": api_key, "url": link}))
        urls_to_try.append((f"http://{clean_site}/api", {"api": api_key, "url": link}))

    timeout = aiohttp.ClientTimeout(total=15)
    connector = aiohttp.TCPConnector(ssl=False)
    
    for endpoint, params in urls_to_try:
        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(endpoint, params=params) as response:
                    try:
                        data = await response.json(content_type=None)
                        if isinstance(data, dict):
                            if data.get("status") in ("success", 200, "200", True) or "shortenedUrl" in data:
                                res_url = data.get("shortenedUrl") or data.get("shortened_url") or data.get("url") or data.get("short") or data.get("link")
                                if res_url and str(res_url).startswith("http"):
                                    return str(res_url).strip()
                            if isinstance(data.get("data"), dict):
                                nested_url = data["data"].get("short_url") or data["data"].get("url") or data["data"].get("shortenedUrl")
                                if nested_url and str(nested_url).startswith("http"):
                                    return str(nested_url).strip()
                            for key in ("shortenedUrl", "shortened_url", "short_url", "url", "link", "shortlink", "result"):
                                val = data.get(key)
                                if val and isinstance(val, str) and val.startswith("http"):
                                    return val.strip()
                    except Exception:
                        text_res = (await response.text()).strip()
                        if text_res.startswith("http://") or text_res.startswith("https://"):
                            return text_res
        except Exception:
            continue
            
    return link


async def validate_shortener_token(site_clean: str, api_token: str) -> bool:
    api_token = (api_token or "").strip()
    if not api_token:
        return False
    if api_token.startswith(("http://", "https://", "www.", "/", "@")) or "/" in api_token or " " in api_token:
        return False
    if len(api_token) < 5:
        return False
    
    test_link = "https://telegram.org"
    dummy_user = {"base_site": site_clean, "shortener_api": api_token}
    try:
        shortened = await get_short_link(dummy_user, test_link)
        if shortened and shortened != test_link and str(shortened).startswith("http"):
            return True
    except Exception:
        pass
    return False


def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    try:
        size = float(size)
    except Exception:
        return "Unknown"
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])


def format_caption(custom_caption: str, media=None, source_msg=None, default_caption=None) -> str:
    if not custom_caption:
        return default_caption
    
    file_name = ""
    file_size = ""
    orig_caption = ""
    
    if source_msg:
        orig_caption = getattr(source_msg, "caption", "") or getattr(source_msg, "text", "") or ""
        if not media and getattr(source_msg, "media", None):
            media = getattr(source_msg, source_msg.media.value, None)
            
    if media:
        file_name = getattr(media, "file_name", "") or getattr(media, "title", "") or ""
        sz = getattr(media, "file_size", None)
        if sz is not None:
            try:
                file_size = get_size(sz)
            except Exception:
                file_size = str(sz)
    
    if not file_name and orig_caption:
        first_line = orig_caption.strip().splitlines()[0]
        file_name = first_line[:60]
    if not file_name:
        file_name = "File"
        
    res = (
        custom_caption
        .replace("{file_name}", file_name)
        .replace("{file_size}", file_size)
        .replace("{caption}", orig_caption)
        .replace("{file_caption}", orig_caption)
    )
    return res


async def get_user(user_id):
    user_id = int(user_id)
    if mongo_db is None:
        return {"user_id": user_id, "shortener_api": None, "base_site": None}
    user = mongo_db.user.find_one({"user_id": user_id})
    if not user:
        res = {
            "user_id": user_id,
            "shortener_api": None,
            "base_site": None,
        }
        mongo_db.user.insert_one(res)
        user = mongo_db.user.find_one({"user_id": user_id})
    return user or {"user_id": user_id, "shortener_api": None, "base_site": None}


async def update_user_info(user_id, value: dict):
    if mongo_db is None:
        return
    user_id = int(user_id)
    myquery = {"user_id": user_id}
    newvalues = {"$set": value}
    mongo_db.user.update_one(myquery, newvalues, upsert=True)
