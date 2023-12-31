# bot/database.py

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

DATABASE_URL = "sqlite:///bot_database.db"
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
metadata = MetaData()

# Описание таблиц
users_table = Table('users', metadata,
                    Column('id', Integer, primary_key=True),
                    Column('username', String),
                    Column('first_name', String),
                    Column('last_name', String)
                    )

queries_table = Table('queries', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('user_id', Integer, ForeignKey('users.id')),
                      Column('text', String),
                      Column('response', String),
                      Column('timestamp', DateTime, default=datetime.utcnow)
                      )

metadata.create_all(engine)

class DatabaseManager:
    def __init__(self):
        self.session = None  # Инициализируем атрибут здесь
        self.session = scoped_session(Session)
        
    def add_or_update_user(self, user_id, username, first_name, last_name):
        with self.session() as session:
            stmt = users_table.insert().values(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            try:
                session.execute(stmt)
                session.commit()
            except IntegrityError:
                session.rollback()
                stmt = users_table.update().where(users_table.c.id == user_id).values(
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.execute(stmt)
                session.commit()

    def add_query(self, user_id, text, response):
        with self.session() as session:
            new_query = queries_table.insert().values(
                user_id=user_id,
                text=text,
                response=response,
                timestamp=datetime.utcnow()
            )
            session.execute(new_query)
            session.commit()

    def __del__(self):
        self.session.remove()