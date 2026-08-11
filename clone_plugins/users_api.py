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
    api_key = user.get("shortener_api")
    base_site = (user.get("base_site") or "").strip().rstrip("/")
    if not api_key or not base_site:
        return link
    if not base_site.startswith(("http://", "https://")):
        base_site = "https://" + base_site
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_site}/api", params={"api": api_key, "url": link}) as response:
                data = await response.json(content_type=None)
                if isinstance(data, dict) and data.get("status") == "success":
                    return data.get("shortenedUrl") or data.get("shortened_url") or link
    except Exception:
        pass
    return link
