# bot/database/models.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    chat_id = Column(Integer)  # Используйте Integer или BigInteger
    first_name = Column(String)
    last_name = Column(String)
    is_premium = Column(Boolean, default=False)
    premium_expiration = Column(DateTime)
    last_message_time = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0, nullable=True)
    last_feedback_time = Column(DateTime, nullable=True)

class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User")
    text = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
