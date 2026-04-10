from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime


def _password_len_bytes(p: str) -> int:
    return len((p or "").encode("utf-8"))


# ================================
# Schema para criar usuário
# ================================
class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_max_72_bytes(cls, v: str):
        if _password_len_bytes(v) > 72:
            raise ValueError(
                "Senha muito longa. O limite é 72 bytes (bcrypt). "
                "Use uma senha menor (evite textos longos, emojis e muitos acentos)."
            )
        return v


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

    @field_validator("password")
    @classmethod
    def validate_password_max_72_bytes(cls, v: str):
        if _password_len_bytes(v) > 72:
            raise ValueError(
                "Senha muito longa. O limite é 72 bytes (bcrypt). "
                "Use uma senha menor."
            )
        return v


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


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


from pydantic import BaseModel
from datetime import datetime


class GameBase(BaseModel):
    nome: str
    descricao: str = ""
    dropbox_token: str
    capa_url: str = ""

    # Requisitos mínimos
    min_os: str = ""
    min_cpu: str = ""
    min_ram_gb: int | None = None
    min_gpu: str = ""
    min_directx: str = ""
    min_storage_gb: int | None = None
    min_notes: str = ""

    # Requisitos recomendados
    rec_os: str = ""
    rec_cpu: str = ""
    rec_ram_gb: int | None = None
    rec_gpu: str = ""
    rec_directx: str = ""
    rec_storage_gb: int | None = None
    rec_notes: str = ""


class GameCreate(GameBase):
    pass


class GameUpdate(BaseModel):
    nome: str
    descricao: str = ""
    dropbox_token: str
    capa_url: str = ""

    # Requisitos mínimos
    min_os: str = ""
    min_cpu: str = ""
    min_ram_gb: int | None = None
    min_gpu: str = ""
    min_directx: str = ""
    min_storage_gb: int | None = None
    min_notes: str = ""

    # Requisitos recomendados
    rec_os: str = ""
    rec_cpu: str = ""
    rec_ram_gb: int | None = None
    rec_gpu: str = ""
    rec_directx: str = ""
    rec_storage_gb: int | None = None
    rec_notes: str = ""


class GameResponse(GameBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True