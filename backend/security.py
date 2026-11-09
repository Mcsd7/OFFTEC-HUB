import secrets
from .config import TOKEN_PATH


def session_token() -> str:
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if len(token) >= 40:
            return token
    token = secrets.token_urlsafe(36)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except OSError:
        pass
    return token
