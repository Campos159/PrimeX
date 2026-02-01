import os
from dotenv import load_dotenv
import dropbox

# Carrega variáveis do .env
load_dotenv()

# Pega o token do .env
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")

if not DROPBOX_ACCESS_TOKEN:
    print("❌ Token não encontrado no .env")
    exit()

try:
    # Inicializa a instância do Dropbox
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

    # Testa acesso com uma chamada simples
    conta = dbx.users_get_current_account()
    print("✅ Token VÁLIDO!")
    print("📄 Nome da conta:", conta.name.display_name)
    print("✉️ Email:", conta.email)

except Exception as e:
    print("❌ Erro ao validar o token:", e)
