import os
import hashlib
import requests

def get_cache_dir(app_name="PrimeX"):
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    cache_dir = os.path.join(base, app_name, "cache", "covers")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def cover_filename(game_id: int, url: str) -> str:
    # nome fixo por jogo, e hash do url pra evitar conflito se trocar
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"game_{game_id}_{h}.jpg"

def get_or_download_cover(game_id: int, url: str, timeout=15) -> str | None:
    if not url:
        return None

    cache_dir = get_cache_dir()
    filename = cover_filename(game_id, url)
    path = os.path.join(cache_dir, filename)

    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception:
        return None
