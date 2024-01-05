# bot/utils/helpers.py

import logging
from bot.api.freekassa import send_telegram_notification, get_chat_id_for_user
from config.settings import ADMIN_TELEGRAM_ID

def send_telegram_notification_to_admin(message, db_manager):
    admin_chat_id = get_chat_id_for_user(ADMIN_TELEGRAM_ID, db_manager)
    if admin_chat_id:
        send_telegram_notification(ADMIN_TELEGRAM_ID, message, db_manager)
    else:
        logging.error(f"Chat ID for admin (ID: {ADMIN_TELEGRAM_ID}) not found.")

def send_feedback_to_admin(user, feedback, db_manager):
    try:
        message = f"Предложение об улучшении от пользователя @{user.username} ({user.first_name} {user.last_name}): {feedback}"
        send_telegram_notification_to_admin(message, db_manager)
    except Exception as e:
        logging.error(f"Error in send_feedback_to_admin: {e}")
