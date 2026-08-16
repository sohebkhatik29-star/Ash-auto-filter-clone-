# © Telegram: @movies_1780
# ASH FILE STORE & CLONE MANAGER

import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from config import CLONE_DB_URI, CDB_NAME

_client = AsyncIOMotorClient(CLONE_DB_URI) if CLONE_DB_URI else None
_db = _client[CDB_NAME] if _client else None
col = _db["users"] if _db else None

async def get_user(user_id):
    user_id = int(user_id)
    if col is None:
        return {"user_id": user_id, "shortener_api": None, "base_site": None,
                "verify_enabled": False, "verify_ttl": 86400}
    user = await col.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "shortener_api": None, "base_site": None,
                "verify_enabled": False, "verify_ttl": 86400,
                "force_channels": [], "caption": None, "buttons": [],
                "protect_content": False}
        await col.insert_one(user)
    return user

async def update_user_info(user_id, value: dict):
    if col is not None:
        await col.update_one({"user_id": int(user_id)}, {"$set": value}, upsert=True)

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
                    # Check text or JSON
                    try:
                        data = await response.json(content_type=None)
                        if isinstance(data, dict):
                            # Standard AdLinkFly / Droplink / VPLink / GPLinks format
                            if data.get("status") in ("success", 200, "200", True) or "shortenedUrl" in data:
                                res_url = data.get("shortenedUrl") or data.get("shortened_url") or data.get("url") or data.get("short") or data.get("link")
                                if res_url and str(res_url).startswith("http"):
                                    return str(res_url).strip()
                            # Nested data object
                            if isinstance(data.get("data"), dict):
                                nested_url = data["data"].get("short_url") or data["data"].get("url") or data["data"].get("shortenedUrl")
                                if nested_url and str(nested_url).startswith("http"):
                                    return str(nested_url).strip()
                            # Direct key check
                            for key in ("shortenedUrl", "shortened_url", "short_url", "url", "link", "shortlink", "result"):
                                val = data.get(key)
                                if val and isinstance(val, str) and val.startswith("http"):
                                    return val.strip()
                    except Exception:
                        # Maybe plain text URL returned
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
    # If user pasted a URL or invalid characters
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
