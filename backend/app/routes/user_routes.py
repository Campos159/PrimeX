from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas, database, crud
from fastapi import status
from app.security import verify_password, create_access_token
from app.models import User
from app.schemas import Login, Token

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Lista de códigos válidos (será controlado por admin futuramente)
valid_activation_codes = {"ABC123", "XPTO456", "GAMEX2025"}

@router.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if user.activation_code not in valid_activation_codes:
        raise HTTPException(status_code=403, detail="Código de ativação inválido")

    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    return crud.create_user(db, user)

@router.post("/login", response_model=Token)
def login(user: Login, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    token = create_access_token(data={"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}