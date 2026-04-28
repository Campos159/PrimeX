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
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

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
@app.post("/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    # Autentica usuário usando crud
    db_user = crud.authenticate_user(db, email=user.email, password=user.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Email ou senha incorretos")

    now = datetime.utcnow()

    # pega o token/plano ativo mais recente do usuário
    tok = (
        db.query(TokenDB)
        .filter(
            TokenDB.user_id == db_user.id,
            TokenDB.active == True
        )
        .order_by(TokenDB.activated_at.desc())
        .first()
    )

    plan = "Nenhum"
    plan_active = False
    expires_at = None
    token_value = ""

    if tok:
        token_value = tok.token
        plan = tok.type
        expires_at = tok.expires_at.isoformat() if tok.expires_at else None

        if tok.expires_at:
            plan_active = tok.expires_at > now
        else:
            # sem expiração = permanente
            plan_active = True

    return {
        "id": db_user.id,
        "nome": db_user.nome,
        "email": db_user.email,
        "is_active": db_user.is_active,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
        "token": token_value,
        "plan": plan,
        "plan_active": plan_active,
        "expires_at": expires_at
    }

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

    # se já for URL completa (CDN/R2), mantém como está
    if p.startswith("http://") or p.startswith("https://"):
        return p

    if "dropbox.com" in p:
        raise HTTPException(
            status_code=400,
            detail="Use apenas o CAMINHO do arquivo no Dropbox. Ex: /jogos/Arquivo.zip"
        )

    if not p.startswith("/"):
        p = "/" + p

    return p

DROPBOX_APP_FOLDER_NAME = os.getenv("DROPBOX_APP_FOLDER_NAME", "")  # ex: "PrimeX"
DROPBOX_BASE_DIR = "/jogos/jogos"  # sua pasta lógica padrão

DROPBOX_MODE = os.getenv("DROPBOX_MODE", "app_folder")  # "app_folder" ou "full"

def dropbox_base_dir() -> str:
    if DROPBOX_MODE == "full":
        # No modo full, você usa o caminho real da conta
        return DROPBOX_BASE_DIR
    # No modo app_folder, o root já é a pasta do app, então base é relativa ao root do app
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
    exe_principal: str | None = None
    capa_url: str | None = None
    banner_url: str | None = None
    screenshot_1_url: str | None = None
    screenshot_2_url: str | None = None

    # mínimos
    min_os: str = ""
    min_cpu: str = ""
    min_ram_gb: int | None = None
    min_gpu: str = ""
    min_directx: str = ""
    min_storage_gb: int | None = None
    min_notes: str = ""

    # recomendados
    rec_os: str = ""
    rec_cpu: str = ""
    rec_ram_gb: int | None = None
    rec_gpu: str = ""
    rec_directx: str = ""
    rec_storage_gb: int | None = None
    rec_notes: str = ""

class TokenRequest(BaseModel):
    type: str

class AvatarCreate(BaseModel):
    nome: str
    image_url: str
    is_active: bool = True


class AvatarUpdate(BaseModel):
    nome: str
    image_url: str
    is_active: bool = True

# ================================
# ROTAS - JOGOS
# ================================
@app.post("/admin/adicionar_avatar")
def adicionar_avatar(avatar: AvatarCreate, db: Session = Depends(get_db)):
    novo = models.Avatar(
        nome=avatar.nome,
        image_url=avatar.image_url,
        is_active=avatar.is_active
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "message": "Avatar adicionado com sucesso",
        "avatar": {
            "id": novo.id,
            "nome": novo.nome,
            "image_url": novo.image_url,
            "is_active": novo.is_active
        }
    }

@app.get("/admin/listar_avatars")
def listar_avatars(db: Session = Depends(get_db)):
    avatars = db.query(models.Avatar).order_by(models.Avatar.id.desc()).all()

    return {
        "avatars": [
            {
                "id": a.id,
                "nome": a.nome,
                "image_url": a.image_url,
                "is_active": a.is_active
            }
            for a in avatars
        ]
    }

@app.get("/avatars/disponiveis")
def avatars_disponiveis(db: Session = Depends(get_db)):
    avatars = (
        db.query(models.Avatar)
        .filter(models.Avatar.is_active == True)
        .order_by(models.Avatar.id.desc())
        .all()
    )

    return {
        "avatars": [
            {
                "id": a.id,
                "nome": a.nome,
                "image_url": a.image_url
            }
            for a in avatars
        ]
    }

@app.put("/admin/editar_avatar/{avatar_id}")
def editar_avatar(avatar_id: int, avatar: AvatarUpdate, db: Session = Depends(get_db)):
    db_avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()

    if not db_avatar:
        raise HTTPException(status_code=404, detail="Avatar não encontrado")

    db_avatar.nome = avatar.nome
    db_avatar.image_url = avatar.image_url
    db_avatar.is_active = avatar.is_active

    db.commit()
    db.refresh(db_avatar)

    return {
        "message": "Avatar atualizado com sucesso",
        "avatar": {
            "id": db_avatar.id,
            "nome": db_avatar.nome,
            "image_url": db_avatar.image_url,
            "is_active": db_avatar.is_active
        }
    }

@app.delete("/admin/deletar_avatar/{avatar_id}")
def deletar_avatar(avatar_id: int, db: Session = Depends(get_db)):
    db_avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()

    if not db_avatar:
        raise HTTPException(status_code=404, detail="Avatar não encontrado")

    db.delete(db_avatar)
    db.commit()

    return {"message": "Avatar deletado com sucesso"}

@app.post("/admin/adicionar_jogo")
def adicionar_jogo(jogo: GameCreate, db: Session = Depends(get_db)):

    dropbox_path = normalizar_dropbox_path(jogo.dropbox_token)

    novo = models.Game(
        nome=jogo.nome,
        descricao=jogo.descricao,
        dropbox_token=dropbox_path,
        exe_principal=jogo.exe_principal or "",
        capa_url=jogo.capa_url or "",
        banner_url=jogo.banner_url or "",
        screenshot_1_url=jogo.screenshot_1_url or "",
        screenshot_2_url=jogo.screenshot_2_url or "",

        min_os=jogo.min_os,
        min_cpu=jogo.min_cpu,
        min_ram_gb=jogo.min_ram_gb,
        min_gpu=jogo.min_gpu,
        min_directx=jogo.min_directx,
        min_storage_gb=jogo.min_storage_gb,
        min_notes=jogo.min_notes,

        rec_os=jogo.rec_os,
        rec_cpu=jogo.rec_cpu,
        rec_ram_gb=jogo.rec_ram_gb,
        rec_gpu=jogo.rec_gpu,
        rec_directx=jogo.rec_directx,
        rec_storage_gb=jogo.rec_storage_gb,
        rec_notes=jogo.rec_notes
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
            "exe_principal": j.exe_principal,
            "capa_url": j.capa_url,
            "banner_url": j.banner_url,
            "screenshot_1_url": j.screenshot_1_url,
            "screenshot_2_url": j.screenshot_2_url,

            "min_os": j.min_os,
            "min_cpu": j.min_cpu,
            "min_ram_gb": j.min_ram_gb,
            "min_gpu": j.min_gpu,
            "min_directx": j.min_directx,
            "min_storage_gb": j.min_storage_gb,
            "min_notes": j.min_notes,

            "rec_os": j.rec_os,
            "rec_cpu": j.rec_cpu,
            "rec_ram_gb": j.rec_ram_gb,
            "rec_gpu": j.rec_gpu,
            "rec_directx": j.rec_directx,
            "rec_storage_gb": j.rec_storage_gb,
            "rec_notes": j.rec_notes
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
    db_jogo.dropbox_token = dropbox_path
    db_jogo.exe_principal = jogo.exe_principal or ""
    db_jogo.capa_url = jogo.capa_url or ""
    db_jogo.banner_url = jogo.banner_url or ""
    db_jogo.screenshot_1_url = jogo.screenshot_1_url or ""
    db_jogo.screenshot_2_url = jogo.screenshot_2_url or ""

    db_jogo.min_os = jogo.min_os
    db_jogo.min_cpu = jogo.min_cpu
    db_jogo.min_ram_gb = jogo.min_ram_gb
    db_jogo.min_gpu = jogo.min_gpu
    db_jogo.min_directx = jogo.min_directx
    db_jogo.min_storage_gb = jogo.min_storage_gb
    db_jogo.min_notes = jogo.min_notes

    db_jogo.rec_os = jogo.rec_os
    db_jogo.rec_cpu = jogo.rec_cpu
    db_jogo.rec_ram_gb = jogo.rec_ram_gb
    db_jogo.rec_gpu = jogo.rec_gpu
    db_jogo.rec_directx = jogo.rec_directx
    db_jogo.rec_storage_gb = jogo.rec_storage_gb
    db_jogo.rec_notes = jogo.rec_notes

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
from fastapi.responses import StreamingResponse, RedirectResponse

@app.get("/jogos/{jogo_id}/download")
def baixar_jogo(jogo_id: int, user_id: int, db: Session = Depends(get_db)):
    # valida plano
    if not usuario_tem_plano_ativo(user_id, db):
        raise HTTPException(status_code=403, detail="Usuário sem plano ativo")

    jogo = db.query(models.Game).filter(models.Game.id == jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    arquivo_ref = (jogo.dropbox_token or "").strip()

    if not arquivo_ref:
        raise HTTPException(status_code=404, detail="Jogo sem arquivo configurado")

    # =========================
    # NOVO: se for link HTTP(S), redireciona pro CDN/R2
    # =========================
    if arquivo_ref.startswith("http://") or arquivo_ref.startswith("https://"):
        return RedirectResponse(url=arquivo_ref, status_code=302)

    # =========================
    # ANTIGO: fallback Dropbox
    # =========================
    dropbox_path = dropbox_full_path(arquivo_ref)

    try:
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
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(md.size)
            }
        )

    except dropbox.exceptions.ApiError as e:
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado no Dropbox: {e}")

    except dropbox.exceptions.AuthError:
        raise HTTPException(status_code=500, detail="Dropbox token inválido/expirado no servidor")

    except Exception as e:
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
