import uuid
import asyncio

_USER_SESSIONS = {}

def start_user_session(user_id: int, action_name: str) -> str:
    user_id = int(user_id)
    token = f"{action_name}:{uuid.uuid4().hex}"
    _USER_SESSIONS[user_id] = token
    return token

def is_user_session_active(user_id: int, token: str) -> bool:
    user_id = int(user_id)
    return _USER_SESSIONS.get(user_id) == token

def clear_user_session(user_id: int):
    user_id = int(user_id)
    _USER_SESSIONS.pop(user_id, None)

def cancel_all_listeners(client, chat_id, user_id=None):
    if user_id is None:
        user_id = chat_id
    clear_user_session(user_id)
    try:
        if hasattr(client, "stop_listening"):
            try:
                client.stop_listening(chat_id=chat_id, user_id=user_id)
            except Exception:
                try:
                    client.stop_listening(chat_id=chat_id)
                except Exception:
                    pass
    except Exception:
        pass
    for attr in ("_listeners", "listeners"):
        try:
            d = getattr(client, attr, None)
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k == chat_id or (user_id and k == user_id) or (isinstance(k, tuple) and (chat_id in k or (user_id and user_id in k))):
                        item = d.pop(k, None)
                        if item:
                            items = item if isinstance(item, (list, tuple, set)) else [item]
                            for fut in items:
                                try:
                                    if hasattr(fut, "cancel"): fut.cancel()
                                    elif hasattr(fut, "set_exception"): fut.set_exception(asyncio.CancelledError())
                                except Exception:
                                    pass
        except Exception:
            pass
