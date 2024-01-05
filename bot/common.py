# bot/common.py

from bot.database.manager import DatabaseManager
from config.settings import MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR
import logging

db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

def check_message_limit(user_id, context):
    user_message_count = context.user_data.get(f'message_count_{user_id}', 0)
    if db_manager.check_premium_status(user_id):
        return user_message_count >= 10  # Лимит для премиум-пользователей
    else:
        return user_message_count >= 1  # Лимит для обычных пользователей

def show_user_status(update, context, user_id):
    try:
        user = db_manager.get_user_by_id(user_id)
        if user:
            remaining_questions = (MAX_QUESTIONS_PER_HOUR_PREMIUM if user.is_premium else MAX_QUESTIONS_PER_HOUR_REGULAR) - user.message_count
            status_msg = f"📌 Условия использования:\n- Вопросов осталось: {remaining_questions} в этот час\n- Премиум статус: {'Активен' if user.is_premium else 'Не активен'}"
            update.message.reply_text(status_msg)
    except Exception as e:
        logging.error(f"Error in show_user_status: {e}")
        update.message.reply_text("Произошла ошибка при отображении статуса.")