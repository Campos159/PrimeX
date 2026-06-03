import os
import subprocess
import requests
from pathlib import Path

PRIMEX_DIR = Path(os.getenv("LOCALAPPDATA", "..")) / "PrimeX"
REDIST_DIR = PRIMEX_DIR / "redist_cache"
MARKER_FILE = REDIST_DIR / "visual_cpp_instalado.ok"


DEPENDENCIAS = [
    {
        "nome": "Visual C++ 2015-2022 x64",
        "arquivo": "VC_redist.x64.exe",
        "url": "https://cdn.apiprimex.online/redistributables/VC_redist.x64.exe",
        "args": ["/install", "/quiet", "/norestart"],
    },
    {
        "nome": "Visual C++ 2015-2022 x86",
        "arquivo": "VC_redist.x86.exe",
        "url": "https://cdn.apiprimex.online/redistributables/VC_redist.x86.exe",
        "args": ["/install", "/quiet", "/norestart"],
    },
]


def baixar_arquivo(url: str, destino: Path) -> bool:
    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists() and destino.stat().st_size > 100_000:
        return True

    try:
        with requests.get(url, stream=True, timeout=(20, 600)) as r:
            r.raise_for_status()

            with open(destino, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        return True

    except Exception as e:
        print(f"[PrimeX] Erro ao baixar {destino.name}: {e}")
        return False


def instalar_visual_cpp(forcar: bool = False) -> bool:
    REDIST_DIR.mkdir(parents=True, exist_ok=True)

    if MARKER_FILE.exists() and not forcar:
        print("[PrimeX] Visual C++ já instalado anteriormente.")
        return True

    sucesso = True

    for dep in DEPENDENCIAS:
        caminho = REDIST_DIR / dep["arquivo"]

        if not baixar_arquivo(dep["url"], caminho):
            sucesso = False
            continue

        try:
            resultado = subprocess.run(
                [str(caminho), *dep["args"]],
                cwd=str(REDIST_DIR),
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            print(f"[PrimeX] {dep['nome']} retorno: {resultado.returncode}")

            # 0    = sucesso
            # 1638 = já existe uma versão instalada
            # 3010 = instalado, reinicialização recomendada
            if resultado.returncode not in (0, 1638, 3010):
                sucesso = False

        except Exception as e:
            print(f"[PrimeX] Erro ao instalar {dep['nome']}: {e}")
            sucesso = False

    if sucesso:
        MARKER_FILE.write_text("ok", encoding="utf-8")

    return sucesso