from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


# ================================
# Schema para criar usuário
# ================================
class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)  # pode ser maior agora


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
    password: str = Field(min_length=1, max_length=256)


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
# Token para autenticação
# ================================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# (Opcional) Se você ainda usa esse schema em algum lugar:
class Login(BaseModel):
    email: str
    password: str
