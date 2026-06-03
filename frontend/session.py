# session.py
import os, json

BASE_DIR = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
APP_DIR = os.path.join(BASE_DIR, "PrimeX")
SESSION_PATH = os.path.join(APP_DIR, "session.json")

def load_session() -> dict:
    try:
        if os.path.exists(SESSION_PATH):
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_session(data: dict) -> None:
    os.makedirs(APP_DIR, exist_ok=True)

    safe_data = {
        "id": data.get("id"),
        "nome": data.get("nome"),
        "email": data.get("email"),
        "is_active": data.get("is_active", True),
    }

    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(safe_data, f, ensure_ascii=False, indent=2)

def clear_session() -> None:
    try:
        if os.path.exists(SESSION_PATH):
            os.remove(SESSION_PATH)
    except Exception:
        pass
