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

print("✅ CARREGOU app/main.py")


# ================================
# BANCO DE DADOS (SQLite)
# ================================
from app.database import SessionLocal, engine  # ✅ usa o mesmo engine/Base do projeto

# Cria tabelas UMA vez, no mesmo banco
models.Base.metadata.create_all(bind=engine)


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

@app.get("/debug/db")
def debug_db():
    return {
        "DATABASE_URL": DATABASE_URL,
        "cwd": os.getcwd(),
        "write_test": _write_test()
    }

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

class TokenDB(models.Base):
    __tablename__ = "tokens"

    token = Column(String(64), primary_key=True, index=True)
    type = Column(String(20), nullable=False)
    active = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)



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


# ================================
# CONFIGURAÇÕES DO DROPBOX
# ================================
DROPBOX_TOKEN = "SEU_TOKEN_AQUI"
DROPBOX_FOLDER = "/jogos"
dbx = dropbox.Dropbox(DROPBOX_TOKEN)

def transformar_link_dropbox(link: str) -> str:
    if "dropbox.com" in link:
        return link.replace("?dl=0", "?dl=1").replace("www.dropbox.com", "dl.dropboxusercontent.com")
    return link

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
    dropbox_token = transformar_link_dropbox(jogo.dropbox_token)
    novo = models.Game(
        nome=jogo.nome,
        descricao=jogo.descricao,
        dropbox_token=dropbox_token,
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
    db_jogo.nome = jogo.nome
    db_jogo.descricao = jogo.descricao
    db_jogo.dropbox_token = transformar_link_dropbox(jogo.dropbox_token)
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
def baixar_jogo(jogo_id: int, db: Session = Depends(get_db)):
    jogo = db.query(models.Game).filter(models.Game.id == jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    link = jogo.dropbox_token
    try:
        r = requests.get(link, stream=True)
        r.raise_for_status()
        return StreamingResponse(
            r.iter_content(chunk_size=1024*1024),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={jogo.nome}.rar"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao baixar: {e}")



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
    token_db.active = True
    token_db.activated_at = datetime.utcnow()
    token_db.user_id = data.user_id

    db.commit()

    return {
        "message": "Token ativado com sucesso",
        "plano": token_db.type,
        "expires_at": token_db.expires_at
    }
