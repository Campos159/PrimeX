from app.database import engine
from app.models import Base

print("Criando as tabelas no banco de dados...")
Base.metadata.drop_all(bind=engine)  # Garante que não há conflitos antigos
Base.metadata.create_all(bind=engine)
print("✅ Tabelas criadas com sucesso.")