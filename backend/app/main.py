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
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN", "")
if not DROPBOX_TOKEN:
    print("❌ DROPBOX_TOKEN não configurado")
dbx = dropbox.Dropbox(DROPBOX_TOKEN, timeout=120)

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
    "Teste Gratuito": timedelta(hours=3),
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
def dropbox_teste():
    try:
        acc = dbx.users_get_current_account()
        return {"ok": True, "name": acc.name.display_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        expiration = None

        db.add(TokenDB(
            token=token_str,
            type=request.type,
            created_at=now,
            expires_at=None,
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
    dropbox_path = (jogo.dropbox_token or "").strip()
    if not dropbox_path.startswith("/"):
        dropbox_path = "/" + dropbox_path

    try:
        # baixa do dropbox via API oficial (não link público)
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
