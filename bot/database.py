
# bot/database.py

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

DATABASE_URL = "sqlite:///bot_database.db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)

class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    text = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

class DatabaseManager:
    def __init__(self):
        self.session = scoped_session(Session)
    
    def add_or_update_user(self, user_id, username, first_name, last_name):
        try:
            with self.session() as session:
                session.merge(User(id=user_id, username=username, first_name=first_name, last_name=last_name))
                session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in add_or_update_user: {e}")
            session.rollback()
    
    def add_query(self, user_id, text, response):
        try:
            with self.session() as session:
                new_query = Query(user_id=user_id, text=text, response=response)
                session.add(new_query)
                session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in add_query: {e}")
            session.rollback()

    def __del__(self):
        self.session.remove()
