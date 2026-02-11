# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# 1) Permite configurar via env var (melhor na host)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 2) Fallback seguro: usar /tmp (quase sempre gravável em hosts)
    db_dir = os.getenv("DB_DIR", "/tmp/gameprime")
    os.makedirs(db_dir, exist_ok=True)
    DB_PATH = os.path.join(db_dir, "gameprime.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
