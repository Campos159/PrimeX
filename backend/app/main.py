from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import dropbox
import requests
import uuid
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship
from fastapi.responses import StreamingResponse
import traceback
from app import models, schemas, crud
from fastapi.responses import JSONResponse
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from app.models import TokenDB
from app.models import DropboxCreds
from datetime import datetime, timedelta

print("✅ CARREGOU app/main.py")


# ================================
# BANCO DE DADOS (SQLite)
# ================================
from app.database import SessionLocal, engine  # ✅ usa o mesmo engine/Base do projeto

# Cria tabelas UMA vez, no mesmo banco
#Fmodels.Base.metadata.create_all(bind=engine)


# ================================
# FASTAPI
# ================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger( "uvicorn.error" )

import os
from app.database import DATABASE_URL

@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)

def _write_test():
    try:
        # tenta criar um arquivo no mesmo diretório do sqlite quando for sqlite:///...
        if DATABASE_URL.startswith("sqlite:///"):
            path = DATABASE_URL.replace("sqlite:///", "", 1)
            d = os.path.dirname(path)
            testfile = os.path.join(d, ".__writetest__")
            with open(testfile, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(testfile)
            return "ok"
        return "not_sqlite"
    except Exception as e:
        return f"fail: {e}"



@app.get("/health")
def health():
    return {"ok": True}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================================
# ROTAS - USUÁRIOS / REGISTRO
# ================================
@app.post("/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = crud.get_user_by_email(db, user.email)
        if existing_user:
            return JSONResponse(status_code=400, content={"detail": "Usuário já existe"})
        print("DEBUG password repr:", repr(user.password))
        print("DEBUG password bytes:", len(user.password.encode("utf-8")))
        new_user = crud.create_user(db, user)
        return JSONResponse(status_code=200, content={
            "id": new_user.id,
            "nome": new_user.nome,
            "email": new_user.email,
            "is_active": new_user.is_active,
            "created_at": str(new_user.created_at)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": f"Erro interno: {str(e)}"})


# ================================
# Rota de login
# ================================
@app.post("/login", response_model=schemas.UserResponse)
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    # Autentica usuário usando crud
    db_user = crud.authenticate_user(db, email=user.email, password=user.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Email ou senha incorretos")

    # Retorna dados do usuário (id, nome, email, is_active, created_at)
    return db_user

# ================================
# MODELOS ADICIONAIS (Jogos e Tokens)
# ===============================



def ativar_token_db(token_str: str, user_id: int, db: Session):
    token = db.query(TokenDB).filter(
        TokenDB.token == token_str,
        TokenDB.active == False
    ).first()

    if not token:
        return None

    # verifica expiração
    if token.expires_at and token.expires_at < datetime.utcnow():
        return None

    token.active = True
    token.activated_at = datetime.utcnow()
    token.user_id = user_id

    db.commit()
    db.refresh(token)
    return token


from sqlalchemy import desc

@app.get("/admin/listar_usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.id.desc()).all()

    result = []
    now = datetime.utcnow()

    for u in users:
        # pega o token mais recente ATIVADO (ou seja: já usado pelo usuário)
        tok = (
            db.query(TokenDB)
            .filter(TokenDB.user_id == u.id, TokenDB.active == True)
            .order_by(desc(TokenDB.activated_at))
            .first()
        )

        token_info = None
        plano_status = "SEM PLANO"

        if tok:
            token_info = {
                "token": tok.token,
                "type": tok.type,
                "activated_at": tok.activated_at.isoformat() if tok.activated_at else None,
                "expires_at": tok.expires_at.isoformat() if tok.expires_at else None,
            }

            if tok.expires_at:
                if tok.expires_at < now:
                    plano_status = "VENCIDO"
                else:
                    plano_status = "ATIVO"
            else:
                # ativado e sem expiração => permanente
                plano_status = "PERMANENTE"

        # Se usuário estiver banido, status geral vira BANIDO
        user_status = "ATIVO" if getattr(u, "is_active", True) else "BANIDO"

        result.append({
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "is_active": getattr(u, "is_active", True),
            "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
            "user_status": user_status,
            "plano_status": plano_status,
            "token_info": token_info,
        })

    return {"usuarios": result}


@app.put("/admin/banir_usuario/{user_id}")
def banir_usuario(user_id: int, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    u.is_active = False
    db.commit()
    return {"message": "Usuário banido com sucesso", "id": u.id}


@app.put("/admin/desbanir_usuario/{user_id}")
def desbanir_usuario(user_id: int, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    u.is_active = True
    db.commit()
    return {"message": "Usuário desbanido com sucesso", "id": u.id}


def usuario_tem_plano_ativo(user_id: int, db: Session):
    token = db.query(TokenDB).filter(
        TokenDB.user_id == user_id,
        TokenDB.active == True
    ).order_by(TokenDB.created_at.desc()).first()

    if not token:
        return False

    # verifica expiração
    if token.expires_at and token.expires_at < datetime.utcnow():
        return False

    return True


# ================================
# CONFIGURAÇÕES DO DROPBOX
# ================================
DROPBOX_FOLDER = "/jogos"

def normalizar_dropbox_path(p: str) -> str:
    p = (p or "").strip()

    # se alguém colar link público, tenta extrair path automaticamente
    if "dropbox.com" in p:
        # exemplo: https://www.dropbox.com/scl/fi/.../jogos/Arquivo.zip?dl=0
        # aqui você pode exigir path manualmente para simplificar
        raise HTTPException(
            status_code=400,
            detail="Use apenas o CAMINHO do arquivo no Dropbox. Ex: /jogos/Arquivo.zip"
        )

    if not p.startswith("/"):
        p = "/" + p

    return p

DROPBOX_APP_FOLDER_NAME = os.getenv("DROPBOX_APP_FOLDER_NAME", "")  # ex: "PrimeX"
DROPBOX_BASE_DIR = "/jogos/jogos"  # sua pasta lógica padrão

def dropbox_base_dir() -> str:
    # Se seu app for "App folder" no Dropbox, o root real vira /Apps/<NOME_DO_APP>
    if DROPBOX_APP_FOLDER_NAME:
        return f"/Apps/{DROPBOX_APP_FOLDER_NAME}{DROPBOX_BASE_DIR}"
    return DROPBOX_BASE_DIR

def dropbox_full_path(p: str) -> str:
    # Sempre converte para o caminho real no token
    p = normalizar_dropbox_path(p)

    base = dropbox_base_dir().rstrip("/")

    # Se já veio apontando pra Apps ou pro base, não mexe
    if p.startswith("/Apps/") or p.startswith(base + "/") or p == base:
        return p

    # Se veio como /jogos/arquivo.zip, remove /jogos do começo e junta no base real
    if p.startswith("/jogos/"):
        p = p[len("/jogos"):]  # vira /arquivo.zip

    return base + p

def get_dropbox_client(db: Session) -> dropbox.Dropbox:
    creds = db.query(DropboxCreds).order_by(DropboxCreds.id.desc()).first()
    if not creds:
        raise HTTPException(status_code=500, detail="Dropbox não está conectado. Faça OAuth primeiro.")

    # Se não tem expires_at, assume que ainda serve (ou token permanente)
    if creds.expires_at and creds.expires_at <= datetime.utcnow():
        # precisa refresh
        if not creds.refresh_token:
            raise HTTPException(status_code=500, detail="Token expirou e não existe refresh_token. Refaça o OAuth.")

        rr = requests.post(
            "https://api.dropboxapi.com/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
            },
            auth=(DROPBOX_APP_KEY, DROPBOX_APP_SECRET),
            timeout=20
        )
        if rr.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Falha ao renovar token Dropbox: {rr.text}")

        jd = rr.json()
        new_access = jd.get("access_token")
        expires_in = jd.get("expires_in")

        if not new_access:
            raise HTTPException(status_code=500, detail="Refresh não retornou access_token.")

        creds.access_token = new_access
        if expires_in:
            creds.expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        creds.updated_at = datetime.utcnow()
        db.commit()

    return dropbox.Dropbox(creds.access_token, timeout=120)

# ================================
# MODELOS Pydantic
# ================================
class GameCreate(BaseModel):
    nome: str
    descricao: str
    dropbox_token: str
    capa_url: str | None = None

class TokenRequest(BaseModel):
    type: str

# ================================
# ROTAS - JOGOS
# ================================
@app.post("/admin/adicionar_jogo")
def adicionar_jogo(jogo: GameCreate, db: Session = Depends(get_db)):

    dropbox_path = normalizar_dropbox_path(jogo.dropbox_token)

    novo = models.Game(
        nome=jogo.nome,
        descricao=jogo.descricao,
        dropbox_token=dropbox_path,   # ✅ AGORA CORRETO
        capa_url=jogo.capa_url or ""
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {"message": "Jogo adicionado com sucesso", "id": novo.id}

@app.get("/admin/listar_jogos")
def listar_jogos(db: Session = Depends(get_db)):
    jogos = db.query(models.Game).all()
    return {"jogos": [
        {
            "id": j.id,
            "nome": j.nome,
            "descricao": j.descricao,
            "dropbox_token": j.dropbox_token,
            "capa_url": j.capa_url
        } for j in jogos
    ]}

@app.put("/admin/editar_jogo/{jogo_id}")
def editar_jogo(jogo_id: int, jogo: GameCreate, db: Session = Depends(get_db)):

    db_jogo = db.query(models.Game).filter(models.Game.id == jogo_id).first()

    if not db_jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    dropbox_path = normalizar_dropbox_path(jogo.dropbox_token)

    db_jogo.nome = jogo.nome
    db_jogo.descricao = jogo.descricao
    db_jogo.dropbox_token = dropbox_path   # ✅ AGORA CORRETO
    db_jogo.capa_url = jogo.capa_url or ""

    db.commit()

    return {"message": "Jogo atualizado com sucesso"}

@app.delete("/admin/deletar_jogo/{jogo_id}")
def deletar_jogo(jogo_id: int, db: Session = Depends(get_db)):
    db_jogo = db.query(models.Game).filter(models.Game.id == jogo_id).first()
    if not db_jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    db.delete(db_jogo)
    db.commit()
    return {"message": "Jogo deletado com sucesso"}

# ================================
# ROTAS - TOKENS
# ================================
durations = {
    "Teste Gratuito": timedelta(hours=24),
    "Mensal": timedelta(days=30),
    "Trimestral": timedelta(days=90),
    "Anual": timedelta(days=365),
    "Permanente": None
}

@app.get("/admin/listar_tokens")
def listar_tokens(db: Session = Depends(get_db)):
    tokens = db.query(TokenDB).order_by(TokenDB.created_at.desc()).all()

    return {
        "tokens": [
            {
                "token": t.token,
                "type": t.type,
                "created_at": t.created_at.isoformat(),
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "activated_at": t.activated_at.isoformat() if t.activated_at else None,
                "user_id": t.user_id,
                "active": t.active
            }
            for t in tokens
        ]
    }

@app.get("/dropbox/teste")
def dropbox_teste(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    acc = dbx.users_get_current_account()
    return {"ok": True, "name": acc.name.display_name}

import os
import urllib.parse
from fastapi import Request
from fastapi.responses import RedirectResponse

DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", "")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "")
DROPBOX_REDIRECT_URI = "https://apiprimex.online/auth/dropbox/callback"

ADMIN_KEY = os.getenv("ADMIN_KEY", "")

@app.get("/auth/dropbox/start")
def dropbox_start(k: str):
    if not ADMIN_KEY or k != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Não autorizado")

    params = {
        "client_id": DROPBOX_APP_KEY,
        "response_type": "code",
        "redirect_uri": DROPBOX_REDIRECT_URI,
        "token_access_type": "offline",
    }
    url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)

@app.get("/auth/dropbox/callback")
def dropbox_callback(code: str, db: Session = Depends(get_db)):
    r = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": DROPBOX_REDIRECT_URI,
        },
        auth=(DROPBOX_APP_KEY, DROPBOX_APP_SECRET),
        timeout=20
    )
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.text)

    data = r.json()

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")  # pode vir ou não
    token_type = data.get("token_type", "bearer")
    expires_in = data.get("expires_in")        # segundos (geralmente vem)
    scope = data.get("scope")
    account_id = data.get("account_id")

    if not access_token:
        raise HTTPException(status_code=400, detail="Dropbox não retornou access_token.")

    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))

    creds = db.query(DropboxCreds).order_by(DropboxCreds.id.desc()).first()
    if not creds:
        creds = DropboxCreds(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            scope=scope,
            account_id=account_id,
            expires_at=expires_at,
        )
        db.add(creds)
    else:
        creds.access_token = access_token
        # refresh_token às vezes só vem na primeira autorização — não apague se não vier
        if refresh_token:
            creds.refresh_token = refresh_token
        creds.token_type = token_type
        creds.scope = scope
        creds.account_id = account_id
        creds.expires_at = expires_at
        creds.updated_at = datetime.utcnow()

    db.commit()

    return {"ok": True, "message": "Dropbox conectado com sucesso!"}


from fastapi import Body


@app.post("/admin/criar_token")
def criar_token(request: TokenRequest = Body(...), db: Session = Depends(get_db)):
    print("CRIA_TOKEN ✅ MAIN.PY - type:", request.type)

    if request.type not in durations:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido: {request.type}. Aceitos: {list(durations.keys())}"
        )

    qtd = 10
    tokens_criados = []
    now = datetime.utcnow()
    dur = durations[request.type]  # ✅ garante que é timedelta ou None

    for _ in range(qtd):
        token_str = str(uuid.uuid4())

        expiration = (now + dur) if dur else None

        db.add(TokenDB(
            token=token_str,
            type=request.type,
            created_at=now,
            expires_at=expiration,
            active=False
        ))

        tokens_criados.append({
            "token": token_str,
            "type": request.type,
            "expires_at": expiration.isoformat() if expiration else None
        })

    db.commit()
    return {"tokens": tokens_criados, "count": len(tokens_criados)}



# ================================
# ROTAS - DOWNLOAD DE JOGOS
# ================================
@app.get("/jogos/{jogo_id}/download")
def baixar_jogo(jogo_id: int, user_id: int, db: Session = Depends(get_db)):
    # 🔐 valida plano
    if not usuario_tem_plano_ativo(user_id, db):
        raise HTTPException(status_code=403, detail="Usuário sem plano ativo")

    jogo = db.query(models.Game).filter(models.Game.id == jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    # agora jogo.dropbox_token deve ser PATH: /jogos/arquivo.zip
    dropbox_path = dropbox_full_path(jogo.dropbox_token)

    try:
        # baixa do dropbox via API oficial (não link público)
        dbx = get_dropbox_client(db)
        md, res = dbx.files_download(dropbox_path)

        def iterator():
            while True:
                chunk = res.raw.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                yield chunk

        filename = os.path.basename(dropbox_path) or f"{jogo.nome}.zip"

        return StreamingResponse(
            iterator(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except dropbox.exceptions.ApiError as e:
        # arquivo não existe / sem permissão etc
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado no Dropbox: {e}")

    except dropbox.exceptions.AuthError:
        raise HTTPException(status_code=500, detail="Dropbox token inválido/expirado no servidor")

    except Exception as e:
        # fallback
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/dropbox/listar")
def listar_pasta_dropbox(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    try:
        res = dbx.files_list_folder(dropbox_base_dir())
        return {
            "arquivos": [
                {
                    "name": e.name,
                    "path_display": e.path_display
                } for e in res.entries
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/dropbox/root")
def dropbox_root(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    try:
        res = dbx.files_list_folder("")
        return {"entries": [{"name": e.name, "path_display": e.path_display} for e in res.entries]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from dropbox.exceptions import ApiError
from fastapi import HTTPException

@app.get("/admin/dropbox/jogos")
def db_jogos(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    try:
        r = dbx.files_list_folder(dropbox_base_dir())
        return {"entries": [{"name": e.name, "path": e.path_display} for e in r.entries]}
    except ApiError as e:
        # devolve mensagem do Dropbox em vez de 500 genérico
        raise HTTPException(status_code=400, detail=str(e))


import urllib.parse

import urllib.parse

@app.get("/admin/dropbox/exists")
def db_exists(path: str, db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    try:
        path = urllib.parse.unquote(path)   # converte %2F em /
        path = dropbox_full_path(path)      # aplica a base correta (/jogos/jogos ou /Apps/... etc)
        md = dbx.files_get_metadata(path)
        return {"ok": True, "name": md.name, "path": md.path_display}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from dropbox.exceptions import ApiError

@app.get("/admin/dropbox/apps")
def list_apps_root(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    try:
        r = dbx.files_list_folder(path="/Apps")
        return {"entries": [{"name": e.name, "path": getattr(e, "path_display", None)} for e in r.entries]}
    except ApiError as e:
        # em App Folder isso geralmente dá "not_found" ou "no_permission"
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/dropbox/debug")
def dropbox_debug(db: Session = Depends(get_db)):
    dbx = get_dropbox_client(db)
    acc = dbx.users_get_current_account()
    return {
        "account_id": acc.account_id,
        "email": getattr(acc, "email", None),
        "name": acc.name.display_name
    }
# =======================
# ROTAS - Token
# =======================

class TokenActivateRequest(BaseModel):
    token: str
    user_id: int

@app.post("/ativar_token")
def ativar_token_servico(token: str, user_id: int, db: Session = Depends(get_db)):
    ativado = ativar_token_db(token, user_id, db)

    if not ativado:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")

    return {"status": "ok", "plano": ativado.type}


@app.post("/token/ativar")
def ativar_token(data: TokenActivateRequest, db: Session = Depends(get_db)):
    token_db = db.query(TokenDB).filter(TokenDB.token == data.token).first()

    if not token_db:
        raise HTTPException(status_code=404, detail="Token inválido")

    if token_db.active:
        raise HTTPException(status_code=400, detail="Token já utilizado")

    if token_db.expires_at and token_db.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expirado")

    # Marca token como usado
    now = datetime.utcnow()
    dur = durations.get(token_db.type)

    token_db.active = True
    token_db.activated_at = now
    token_db.user_id = data.user_id

    if dur:
        token_db.expires_at = now + dur

    db.commit()

    return {
        "message": "Token ativado com sucesso",
        "plano": token_db.type,
        "expires_at": token_db.expires_at
    }
