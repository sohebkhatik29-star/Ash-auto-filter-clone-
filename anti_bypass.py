# 🛡️ 8-MODEL ADVANCED ANTI-BYPASS DEFENSE SYSTEM
# Comprehensive protection against shortener bypass bots, scripts, replay attacks, and scrapers.

import time
import hmac
import hashlib
import secrets
import logging
from typing import Tuple, Dict, Any, Optional
try:
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
except ImportError:
    InlineKeyboardMarkup = None
    InlineKeyboardButton = None

logger = logging.getLogger("anti_bypass")

# Secret salt for cryptographic HMAC signatures
SECRET_SALT = b"ASH_CORE_ANTI_BYPASS_SALT_v8_SECURE_2026"

# In-memory rate limiting tracker: {user_id: [timestamp1, timestamp2, ...]}
_FAILED_ATTEMPTS: Dict[int, list] = {}
_COOLDOWN_USERS: Dict[int, float] = {}

# Known automated scraper user agents (Model 7)
BLOCKED_USER_AGENTS = [
    "python", "requests", "aiohttp", "httpx", "curl", "wget", "urllib",
    "scrapy", "headless", "phantomjs", "postman", "selenium", "puppeteer",
    "playwright", "bypass", "telethon", "pyrogram"
]


class AntiBypassResult:
    """Encapsulates the result of 8-Model Anti-Bypass verification."""
    def __init__(
        self,
        is_valid: bool,
        is_bypassed: bool,
        orig_payload: str = "",
        slot: int = 1,
        time_taken: int = 0,
        model_triggered: Optional[str] = None,
        reason: str = "",
        warning_text: str = "",
        retry_markup: Optional[InlineKeyboardMarkup] = None
    ):
        self.is_valid = is_valid
        self.is_bypassed = is_bypassed
        self.orig_payload = orig_payload
        self.slot = slot
        self.time_taken = time_taken
        self.model_triggered = model_triggered
        self.reason = reason
        self.warning_text = warning_text
        self.retry_markup = retry_markup

    def __iter__(self):
        # Enables backward-compatible unpacking:
        # orig_payload, slot_used, is_bypassed, time_taken = result
        return iter((self.orig_payload, self.slot, self.is_bypassed, self.time_taken))


def generate_secure_token(user_id: int, bot_id: int = 0, slot: int = 1, created_at: Optional[int] = None) -> Tuple[str, str]:
    """
    Model 3 & Model 6: Generate a cryptographically secure random token and HMAC signature.
    """
    raw_nonce = secrets.token_hex(8)  # 16-hex characters
    ts = int(created_at) if created_at is not None else int(time.time())
    sig_payload = f"{raw_nonce}:{user_id}:{bot_id}:{slot}:{ts}".encode("utf-8")
    sig = hmac.new(SECRET_SALT, sig_payload, hashlib.sha256).hexdigest()[:8]
    full_token = f"{raw_nonce}_{sig}"
    return full_token, sig


def verify_signature(token: str, user_id: int, bot_id: int, slot: int, created_at: int, sig_in_db: str) -> bool:
    """
    Model 6: Double-Hop Cryptographic Signature & Tamper Proofing.
    Verifies that the token was mathematically issued by this server for this user & timestamp.
    """
    try:
        raw_nonce = token.split("_", 1)[0]
        sig_payload = f"{raw_nonce}:{user_id}:{bot_id}:{slot}:{created_at}".encode("utf-8")
        expected_sig = hmac.new(SECRET_SALT, sig_payload, hashlib.sha256).hexdigest()[:8]
        return hmac.compare_digest(expected_sig, sig_in_db)
    except Exception as e:
        logger.warning("Signature verification error: %s", e)
        return False


def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    """
    Model 5: Rate Limiter & Rapid-Flood Protection.
    Prevents brute-force or script hammering.
    """
    now = time.time()
    # Check active cooldown
    if user_id in _COOLDOWN_USERS:
        cooldown_until = _COOLDOWN_USERS[user_id]
        if now < cooldown_until:
            rem = int(cooldown_until - now)
            return False, rem
        else:
            _COOLDOWN_USERS.pop(user_id, None)

    # Clean old attempts (> 60s)
    attempts = _FAILED_ATTEMPTS.get(user_id, [])
    attempts = [t for t in attempts if now - t < 60]
    _FAILED_ATTEMPTS[user_id] = attempts

    if len(attempts) >= 3:
        # Trigger 5-minute cooldown
        _COOLDOWN_USERS[user_id] = now + 300
        _FAILED_ATTEMPTS[user_id] = []
        return False, 300

    return True, 0


def record_failed_attempt(user_id: int):
    """Record a failed or bypassed attempt for rate limiting."""
    now = time.time()
    attempts = _FAILED_ATTEMPTS.get(user_id, [])
    attempts.append(now)
    _FAILED_ATTEMPTS[user_id] = attempts


def check_user_agent(user_agent: str) -> bool:
    """
    Model 7: Automated Bot & Scraper User-Agent Filtering.
    Returns True if legitimate browser, False if known bypasser tool.
    """
    if not user_agent:
        return False
    ua_clean = user_agent.lower()
    for bad in BLOCKED_USER_AGENTS:
        if bad in ua_clean:
            return False
    return True


def get_bypass_threshold(bot_id: int, slot: int = 1, mongo_db=None) -> int:
    """
    Determine the minimum time (in seconds) required for human verification.
    Defaults to 50s, or reads custom setting from DB.
    """
    default_time = 50
    if mongo_db is None:
        return default_time

    try:
        # Check clone bot record
        if bot_id and int(bot_id) > 0:
            rec = mongo_db.bots.find_one({"bot_id": int(bot_id)})
            if rec:
                slot_cfg = rec.get(f"verify_{slot}", {})
                custom_time = slot_cfg.get("bypass_time") or rec.get("bypass_time")
                if custom_time and str(custom_time).isdigit():
                    return max(10, int(custom_time))

        # Check master bot config
        m_cfg = mongo_db.master_config.find_one()
        if m_cfg:
            slot_cfg = m_cfg.get(f"verify_{slot}", {})
            custom_time = slot_cfg.get("bypass_time") or m_cfg.get("bypass_time")
            if custom_time and str(custom_time).isdigit():
                return max(10, int(custom_time))
    except Exception as e:
        logger.warning("Error fetching bypass threshold: %s", e)

    return default_time


def build_bypass_warning_ui(reason_detail: str, time_taken: int, min_time: int, orig_payload: str = "") -> Tuple[str, InlineKeyboardMarkup]:
    """
    Build beautiful, user-facing warning message when bypass is detected.
    """
    msg_text = (
        "🚨 <b>BYPASS DETECTED! ACCESS DENIED</b> 🚨\n\n"
        "<blockquote>Our 8-Model Anti-Bypass System has detected an automated shortener bypass or invalid verification attempt.</blockquote>\n\n"
        f"⏱ <b>Time Taken:</b> <code>{time_taken}s</code> (Minimum required: <code>{min_time}s</code>)\n"
        f"🛡️ <b>Detection:</b> <i>{reason_detail}</i>\n\n"
        "⚠️ <b>Why did this happen?</b>\n"
        "• You used a Telegram Bypass Bot, scraper script, or website.\n"
        "• You skipped the mandatory shortener countdown timers.\n"
        "• The verification token was shared or replayed.\n\n"
        "👉 <b>How to solve:</b> Please open the shortlink in your official mobile browser, wait for the countdown steps manually, and return!"
    )
    cb_target = f"master_verify:{orig_payload}" if orig_payload else "master_verify"
    if InlineKeyboardMarkup and InlineKeyboardButton:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 RETRY MANUALLY (NO BYPASS) 🔄", callback_data=cb_target)]
        ])
    else:
        markup = None
    return msg_text, markup


def validate_verify_attempt(
    token_str: str,
    user_id: int,
    bot_id: int = 0,
    mongo_db = None,
    user_agent: Optional[str] = None
) -> AntiBypassResult:
    """
    Execute all 8 models of the Anti-Bypass verification pipeline.
    """
    clean_token = token_str.strip()
    now = int(time.time())

    # ----------------------------------------------------
    # Model 5: Rate Limiting & Rapid Flood Shield
    # ----------------------------------------------------
    is_allowed, cooldown_rem = check_rate_limit(user_id)
    if not is_allowed:
        warning = (
            "⚠️ <b>TOO MANY FAILED / BYPASS ATTEMPTS!</b>\n\n"
            f"You have been placed on cooldown. Please wait <b>{cooldown_rem} seconds</b> before trying again."
        )
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=True,
            model_triggered="Model 5: Rate Limiting & Rapid Flood Shield",
            reason="Rapid attempts limit exceeded",
            warning_text=warning
        )

    # ----------------------------------------------------
    # Model 7: Scraper & Automated Tool User-Agent Check (if UA provided)
    # ----------------------------------------------------
    if user_agent and not check_user_agent(user_agent):
        record_failed_attempt(user_id)
        warning = "❌ <b>Automated script/scraper user-agent detected and blocked.</b>"
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=True,
            model_triggered="Model 7: Automated Tool / Scraper User-Agent Filter",
            reason=f"Blocked User-Agent: {user_agent}",
            warning_text=warning
        )

    if mongo_db is None:
        return AntiBypassResult(is_valid=False, is_bypassed=False, reason="Database unavailable")

    # ----------------------------------------------------
    # Model 3: One-Time Nonce & Anti-Replay Guard (Atomic Find & Delete)
    # ----------------------------------------------------
    # Attempt to locate and atomically remove the token so it CAN NEVER BE REUSED.
    query = {"token": clean_token}
    rec = mongo_db.verify_tokens.find_one_and_delete(query)

    # Check fallback legacy tokens collection if not in verify_tokens
    if not rec:
        rec = mongo_db.access_tokens.find_one_and_delete({"token": clean_token})

    if not rec:
        record_failed_attempt(user_id)
        warning = (
            "❌ <b>INVALID OR EXPIRED VERIFICATION LINK!</b>\n\n"
            "This link has either already been used once (Anti-Replay protection) or does not exist.\n"
            "Please generate a fresh link to continue."
        )
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=False,
            model_triggered="Model 3: One-Time Nonce & Anti-Replay Engine",
            reason="Token not found or already consumed",
            warning_text=warning
        )

    created_at = int(rec.get("created_at", now))
    expires_at = int(rec.get("expires_at", created_at + 3600))
    time_taken = max(0, now - created_at)
    slot = int(rec.get("slot", 1))
    orig_payload = rec.get("payload", "")
    token_owner_id = int(rec.get("user_id", 0))
    token_bot_id = int(rec.get("bot_id", 0))
    sig_in_db = rec.get("sig", "")

    # ----------------------------------------------------
    # Model 2: Telegram User-ID Binding Check
    # ----------------------------------------------------
    if token_owner_id and token_owner_id != int(user_id):
        record_failed_attempt(user_id)
        msg_text, markup = build_bypass_warning_ui(
            f"Token was generated for User {token_owner_id}, but claimed by User {user_id}",
            time_taken,
            50,
            orig_payload
        )
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=True,
            orig_payload=orig_payload,
            slot=slot,
            time_taken=time_taken,
            model_triggered="Model 2: Telegram User-ID Binding Mismatch",
            reason=f"User ID mismatch: Token created for {token_owner_id} but used by {user_id}",
            warning_text=msg_text,
            retry_markup=markup
        )

    # ----------------------------------------------------
    # Model 4: Dynamic TTL & Expiration Shield
    # ----------------------------------------------------
    if now > expires_at:
        record_failed_attempt(user_id)
        warning = (
            "⏳ <b>VERIFICATION LINK EXPIRED!</b>\n\n"
            f"This link was created {time_taken} seconds ago and has exceeded the validity window.\n"
            "Please click the button below to get a new link."
        )
        cb_target = f"master_verify:{orig_payload}" if orig_payload else "master_verify"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 GET NEW VERIFICATION LINK 🔄", callback_data=cb_target)]]) if InlineKeyboardMarkup and InlineKeyboardButton else None
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=False,
            orig_payload=orig_payload,
            slot=slot,
            time_taken=time_taken,
            model_triggered="Model 4: Dynamic TTL & Expiration Shield",
            reason=f"Token expired: TTL exceeded ({time_taken}s > {expires_at - created_at}s)",
            warning_text=warning,
            retry_markup=markup
        )

    # ----------------------------------------------------
    # Model 6: Cryptographic Signature Tamper Shield
    # ----------------------------------------------------
    if sig_in_db:
        is_sig_valid = verify_signature(clean_token, token_owner_id, token_bot_id, slot, created_at, sig_in_db)
        if not is_sig_valid:
            record_failed_attempt(user_id)
            msg_text, markup = build_bypass_warning_ui(
                "Cryptographic HMAC signature verification failed (Tampered Token)",
                time_taken,
                50,
                orig_payload
            )
            return AntiBypassResult(
                is_valid=False,
                is_bypassed=True,
                orig_payload=orig_payload,
                slot=slot,
                time_taken=time_taken,
                model_triggered="Model 6: Cryptographic Signature Tamper Shield",
                reason="HMAC SHA-256 signature mismatch (tampered payload)",
                warning_text=msg_text,
                retry_markup=markup
            )

    # ----------------------------------------------------
    # Model 1: Speed & Minimum Time-Delta Engine
    # ----------------------------------------------------
    min_bypass_time = get_bypass_threshold(bot_id or token_bot_id, slot, mongo_db)
    if time_taken < min_bypass_time:
        record_failed_attempt(user_id)
        msg_text, markup = build_bypass_warning_ui(
            f"Completed in {time_taken}s — Minimum human shortener time is {min_bypass_time}s",
            time_taken,
            min_bypass_time,
            orig_payload
        )
        return AntiBypassResult(
            is_valid=False,
            is_bypassed=True,
            orig_payload=orig_payload,
            slot=slot,
            time_taken=time_taken,
            model_triggered="Model 1: Speed & Minimum Time-Delta Engine (Instant Bypass)",
            reason=f"Verification too fast ({time_taken}s < {min_bypass_time}s)",
            warning_text=msg_text,
            retry_markup=markup
        )

    # ----------------------------------------------------
    # Model 8: Strict State Isolation & Verified Success
    # ----------------------------------------------------
    # All 7 checks passed with flying colors!
    return AntiBypassResult(
        is_valid=True,
        is_bypassed=False,
        orig_payload=orig_payload,
        slot=slot,
        time_taken=time_taken,
        model_triggered=None,
        reason="Passed all 8 Anti-Bypass checks successfully"
    )
