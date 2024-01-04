
# bot/database.py

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from datetime import datetime
import logging
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    chat_id = Column(Integer)  # Используйте Integer или BigInteger в зависимости от размера id чата
    first_name = Column(String)
    last_name = Column(String)
    is_premium = Column(Boolean, default=False)
    premium_expiration = Column(DateTime)  # Исправлено имя поля
    last_message_time = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0, nullable=True)
    next_message_available = Column(DateTime, nullable=True)
    last_feedback_time = Column(DateTime, nullable=True)  # Добавьте эту строку

class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    text = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

class DatabaseManager:
    def __init__(self, max_questions_premium, max_questions_regular):
        self.session = scoped_session(Session)
        self.max_questions_premium = max_questions_premium
        self.max_questions_regular = max_questions_regular
    
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
                    user.premium_expiration = None  # Имя поля исправлено на premium_expiration

                session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in expire_premium_subscriptions: {e}")
            session.rollback()

    def add_or_update_user(self, user_id, username, first_name, last_name, chat_id):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    # Обновляем существующего пользователя
                    user.username = username
                    user.first_name = first_name
                    user.last_name = last_name
                    user.chat_id = chat_id
                else:
                    # Добавляем нового пользователя
                    new_user = User(id=user_id, username=username, first_name=first_name, last_name=last_name, chat_id=chat_id)
                    session.add(new_user)
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
        if hasattr(self, 'session'):
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
                    user.premium_expiration = expiration_date  # Убедитесь, что имя поля совпадает
                    session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in update_premium_status: {e}")
            session.rollback()

    def check_premium_status(self, user_id):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user and user.is_premium:
                    # Исправлено: использование premium_expiration вместо premium_expiration_date
                    if user.premium_expiration and user.premium_expiration > datetime.now():
                        return True
                return False
        except SQLAlchemyError as e:
            logging.error(f"Database error in check_premium_status: {e}")
            return False
        
    def is_within_message_limit(self, user_id):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False, 0

                now = datetime.now()
                # Обновляем счетчик, если прошел час с момента последнего сообщения
                if user.last_message_time and (now - user.last_message_time).total_seconds() >= 3600:
                    user.message_count = 0
                    session.commit()

                remaining_messages = self.max_questions_premium - user.message_count if user.is_premium else self.max_questions_regular - user.message_count
                return user.message_count < self.max_questions_premium if user.is_premium else user.message_count < self.max_questions_regular, remaining_messages
        except SQLAlchemyError as e:
            logging.error(f"Database error in is_within_message_limit: {e}")
            return False, 0

    def update_message_count(self, user_id):
        try:
            with self.session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if user:
                    user.message_count += 1
                    user.last_message_time = datetime.now()
                    session.commit()
        except SQLAlchemyError as e:
            logging.error(f"Database error in update_message_count: {e}")
            session.rollback()

# db_manager = DatabaseManager()
# users = db_manager.get_all_users()
# queries = db_manager.get_all_queries()

# for user in users:
#     print(f"User ID: {user.id}, Username: {user.username}, Name: {user.first_name} {user.last_name}")

# for query in queries:
#     print(f"Query ID: {query.id}, User ID: {query.user_id}, Text: {query.text}, Response: {query.response}, Timestamp: {query.timestamp}")
