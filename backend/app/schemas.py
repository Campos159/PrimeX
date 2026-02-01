from pydantic import BaseModel, EmailStr
from datetime import datetime

# ================================
# Schema para criar usuário
# ================================
class UserCreate(BaseModel):
    nome: str        # antes era username, agora é "nome" conforme o models.py
    email: EmailStr
    password: str

# ================================
# Schema de resposta ao criar usuário
# ================================
class UserResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr
    is_active: bool
    created_at: datetime

class Config:
    from_attributes = True

# ================================
# Schema para login
# ================================
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# ================================
# Schema para resposta de login
# ================================
class UserOut(BaseModel):
    id: int
    nome: str
    email: EmailStr
    is_active: bool
    created_at: datetime

class Config:
    from_attributes = True

# ================================
# Configuração para Pydantic usar atributos do ORM
# ================================
class Config:
    from_attributes = True

# ================================
# Token para autenticação
# ================================
class Login(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
