
# bot/database.py

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, ForeignKey, Boolean
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
    chat_id = Column(String)  # Add this line for chat ID
    first_name = Column(String)
    last_name = Column(String)
    is_premium = Column(Boolean, default=False)  # Убедитесь, что этот столбец присутствует
    premium_expiration = Column(DateTime)

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
    
    def get_user_by_id(self, user_id):
        try:
            with self.session() as session:
                return session.query(User).filter(User.id == user_id).first()
        except SQLAlchemyError as e:
            logging.error(f"Database error in get_user_by_id: {e}")
            return None

    def expire_premium_subscriptions(self):
        try:
            with self.session() as session:
                # Find all users with expired subscriptions
                expired_users = session.query(User).filter(
                    User.is_premium == True,
                    User.premium_expiration < datetime.now()
                ).all()

                # Update their premium status
                for user in expired_users:
                    user.is_premium = False
                    user.premium_expiration = None

                session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in expire_premium_subscriptions: {e}")
            session.rollback()

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
        
    def get_all_users(self):
        try:
            with self.session() as session:
                return session.query(User).all()
        except SQLAlchemyError as e:
            logging.error(f"Database error in get_all_users: {e}")
            return []

    def get_all_queries(self):
        try:
            with self.session() as session:
                return session.query(Query).all()
        except SQLAlchemyError as e:
            logging.error(f"Database error in get_all_queries: {e}")
            return []
        
    def update_premium_status(self, user_id, is_premium, expiration_date):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    user.is_premium = is_premium
                    user.premium_expiration = expiration_date  # Ensure this matches the column name
                    session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in update_premium_status: {e}")
            session.rollback()

    def check_premium_status(self, user_id):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user and user.is_premium and user.premium_expiration_date > datetime.now():
                    return True
                return False
        except SQLAlchemyError as e:
            logging.error(f"Database error in check_premium_status: {e}")
            return False

# db_manager = DatabaseManager()
# users = db_manager.get_all_users()
# queries = db_manager.get_all_queries()

# for user in users:
#     print(f"User ID: {user.id}, Username: {user.username}, Name: {user.first_name} {user.last_name}")

# for query in queries:
#     print(f"Query ID: {query.id}, User ID: {query.user_id}, Text: {query.text}, Response: {query.response}, Timestamp: {query.timestamp}")
