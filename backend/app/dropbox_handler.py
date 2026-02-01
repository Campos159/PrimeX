import os
import dropbox
from dotenv import load_dotenv

# Caminho ABSOLUTO do .env
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(dotenv_path)

DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")

if not DROPBOX_ACCESS_TOKEN:
    raise ValueError("❌ DROPBOX_ACCESS_TOKEN não foi encontrado no .env")

dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def get_temporary_link(dropbox_path: str) -> str:
    try:
        link = dbx.files_get_temporary_link(dropbox_path)
        return link.link
    except Exception as e:
        raise RuntimeError(f"Erro ao obter link temporário: {e}")


print("🔐 Token carregado:", DROPBOX_ACCESS_TOKEN[:20], "...")  # Não mostra tudo por segurança
