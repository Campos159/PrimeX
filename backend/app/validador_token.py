# validador_token.py
import os
from dotenv import load_dotenv
import dropbox

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

token = os.getenv("DROPBOX_ACCESS_TOKEN")

if not token:
    print("❌ Token não encontrado no .env")
    exit()

try:
    dbx = dropbox.Dropbox(token)
    conta = dbx.users_get_current_account()
    print("✅ Token VÁLIDO")
    print("📄 Nome:", conta.name.display_name)
    print("📧 Email:", conta.email)
except Exception as e:
    print("❌ Token INVÁLIDO ou erro de escopo:", e)
