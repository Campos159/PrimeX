from app.database import SessionLocal
from app import models
from app.security import get_password_hash

# Abra a sessão do banco
db = SessionLocal()

nome = "Admin"
email = "admin@example.com"
senha = "admin123"
codigo_admin = "CODIGO123"

user_existente = db.query(models.User).filter(models.User.email == email).first()

if user_existente:
    print("Usuário já existe!")
else:
    user = models.User(
        username=nome,
        email=email,
        password=get_password_hash(senha),
        activation_code=codigo_admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("Usuário criado com sucesso:", user.email)

db.close()
