import hashlib
import os
import json

VALIDATION_FILE = "downloads/validacoes.json"

def gerar_token_instalacao(jogo_id: str):
    token = hashlib.sha256(f"{jogo_id}_seguro".encode()).hexdigest()
    if not os.path.exists(VALIDATION_FILE):
        with open(VALIDATION_FILE, 'w') as f:
            json.dump({}, f)

    with open(VALIDATION_FILE, 'r+') as f:
        data = json.load(f)
        data[jogo_id] = token
        f.seek(0)
        json.dump(data, f, indent=2)

def validar_acesso(jogo_id: str, token_recebido: str) -> bool:
    if not os.path.exists(VALIDATION_FILE):
        return False

    with open(VALIDATION_FILE, 'r') as f:
        data = json.load(f)
        return data.get(jogo_id) == token_recebido
