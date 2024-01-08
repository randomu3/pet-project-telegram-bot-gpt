# bot/frekassa_api.py

from config import TELEGRAM_BOT_TOKEN
import requests
import logging

def get_chat_id_for_user(user_id, db_manager):
    user = db_manager.get_user_by_id(user_id)
    return user.chat_id if user else None

# Функция для отправки уведомлений в Telegram
def send_telegram_notification(user_id, message, db_manager):
    chat_id = get_chat_id_for_user(user_id, db_manager)
    if not chat_id:
        logging.error(f"Chat ID not found for user {user_id}")
        return
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message
    }
    try:
        response = requests.post(telegram_api_url, data=data)
        if response.status_code == 200:
            logging.info(f"Message successfully sent to user {user_id}")
        else:
            logging.error(f"Failed to send message to user {user_id}, status code: {response.status_code}, response: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram notification: {e}")
