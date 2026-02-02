from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app import models, schemas

import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_password(password: str) -> str:
    """
    bcrypt só usa os primeiros 72 BYTES da senha.
    Para aceitar qualquer tamanho (e evitar erro/colisão), fazemos um pré-hash SHA-256.
    """
    if password is None:
        password = ""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(_prehash_password(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_prehash_password(plain_password), hashed_password)


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = hash_password(user.password)

    db_user = models.User(
        nome=user.nome,
        email=user.email,
        password=hashed_password,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user
