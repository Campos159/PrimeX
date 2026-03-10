import os
import json

BASE_DIR = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(BASE_DIR, "PrimeX")
CONFIG_FILE = os.path.join(CONFIG_DIR, "install_settings.json")

def _default_root() -> str:
    return os.path.join(BASE_DIR, "PrimeX", "games")

def save_install_root(path: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {"install_root": path}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_install_root() -> str:
    if not os.path.exists(CONFIG_FILE):
        root = _default_root()
        save_install_root(root)
        return root

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        root = (data.get("install_root") or "").strip()
        if not root:
            root = _default_root()
            save_install_root(root)
        return root
    except Exception:
        root = _default_root()
        save_install_root(root)
        return root