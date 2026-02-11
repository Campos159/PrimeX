from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  # Certifique-se de que este Base é o mesmo usado no main.py

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=False, index=True)  # Substituindo username por nome
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)
    is_subscribed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")


class Game(Base):
    __tablename__ = "jogos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    descricao = Column(Text, default="")
    dropbox_token = Column(String, nullable=False)
    capa_url = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class TokenDB(Base):
    __tablename__ = "tokens"

    token = Column(String(64), primary_key=True, index=True)
    type = Column(String(20), nullable=False)
    active = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)




class AccessCode(Base):
    __tablename__ = "access_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    used = Column(Boolean, default=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_name = Column(String(50))
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="subscriptions")
