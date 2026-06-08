import os
import json
import base64
import requests
from pathlib import Path
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from api_config import API_BASE
from utils import resource_path


BASE_DIR = Path(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"))
PRIMEX_DIR = BASE_DIR / "PrimeX"
LICENSE_PATH = PRIMEX_DIR / "license.dat"

PUBLIC_KEY_PATH = resource_path(os.path.join("keys", "primex_public_key.pem"))


def _parse_dt(value: str):
    if not value:
        return None

    value = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def _now():
    return datetime.now(timezone.utc)


def _load_public_key() -> Ed25519PublicKey:
    with open(PUBLIC_KEY_PATH, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    if not isinstance(public_key, Ed25519PublicKey):
        raise RuntimeError("Chave pública inválida.")

    return public_key


def _raw_payload(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")


def salvar_licenca(data: dict):
    PRIMEX_DIR.mkdir(parents=True, exist_ok=True)

    with open(LICENSE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def carregar_licenca():
    if not LICENSE_PATH.exists():
        return None

    try:
        with open(LICENSE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return None


def validar_licenca_local(user_id: int) -> bool:
    data = carregar_licenca()

    if not data:
        return False

    payload = data.get("license")
    signature = data.get("signature")

    if not isinstance(payload, dict) or not signature:
        return False

    if int(payload.get("user_id", 0)) != int(user_id):
        return False

    if payload.get("plan_active") is not True:
        return False

    offline_until = _parse_dt(payload.get("offline_until"))

    if not offline_until or offline_until <= _now():
        return False

    try:
        public_key = _load_public_key()
        sig_bytes = base64.urlsafe_b64decode(signature.encode("utf-8"))

        public_key.verify(
            sig_bytes,
            _raw_payload(payload)
        )

        return True

    except Exception:
        return False


def renovar_licenca_online(user_id: int) -> bool:
    try:
        r = requests.get(
            f"{API_BASE}/usuario/{user_id}/offline_license",
            timeout=10
        )

        if r.status_code != 200:
            return False

        data = r.json()

        if not isinstance(data, dict):
            return False

        salvar_licenca(data)

        return validar_licenca_local(user_id)

    except Exception:
        return False


def validar_acesso_usuario(user_id: int) -> bool:
    """
    1. Tenta renovar licença online no servidor.
    2. Se falhar internet/API, usa licença local assinada válida por até 48h.
    """
    if not user_id:
        return False

    if renovar_licenca_online(user_id):
        return True

    return validar_licenca_local(user_id)