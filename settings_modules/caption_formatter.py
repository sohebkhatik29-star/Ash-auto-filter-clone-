"""Caption formatting helper.
Provides format_caption for customizable media captions.
"""
try:
    from clone_plugins.users_api import format_caption
except Exception:
    try:
        from plugins.users_api import format_caption
    except Exception:
        def format_caption(custom_caption: str, media=None, source_msg=None, default_caption=None) -> str:
            if not custom_caption:
                return default_caption or ""
            res = custom_caption
            if source_msg and hasattr(source_msg, "caption") and source_msg.caption:
                res = res.replace("{caption}", str(source_msg.caption))
            if source_msg and hasattr(source_msg, "text") and source_msg.text:
                res = res.replace("{caption}", str(source_msg.text))
            return res

__all__ = ["format_caption"]
