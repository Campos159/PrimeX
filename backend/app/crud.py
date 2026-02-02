from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app import models, schemas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    # schemas.py já validou <= 72 bytes, então aqui não explode.
    hashed_password = pwd_context.hash(user.password)

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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Se chegar aqui, evita estourar 500 e devolve "senha inválida" no login.
        return False


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user
