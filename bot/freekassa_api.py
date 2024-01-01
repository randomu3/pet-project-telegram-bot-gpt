import hashlib
from datetime import datetime
import logging
import requests
import os
from dotenv import load_dotenv
load_dotenv()  # Это загрузит переменные окружения из .env файла

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
MERCHANT_ID = os.getenv('FREEKASSA_MERCHANT_ID')
if MERCHANT_ID is None:
    raise ValueError("Не удалось загрузить MERCHANT_ID из переменных окружения")
SECRET_KEY = os.getenv('FREEKASSA_SECRET_KEY_1')

def generate_payment_link(user_id, amount, merchant_id=MERCHANT_ID, secret_key=SECRET_KEY, currency="RUB", lang="ru"):
    order_id = f"{user_id}-{datetime.now().timestamp()}"

    # Формирование подписи с учетом валюты и языка
    sign_str = f"{merchant_id}:{amount}:{secret_key}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    payment_url = f"https://pay.freekassa.ru/?m={merchant_id}&oa={amount}&o={order_id}&currency={currency}&lang={lang}&s={sign}"
    return payment_url

def get_chat_id_for_user(user_id):
    # Реализация получения chat_id для данного user_id
    user = db_manager.get_user_by_id(user_id)
    return user.chat_id if user else None

# Функция для отправки уведомлений в Telegram
def send_telegram_notification(user_id, message):
    chat_id = get_chat_id_for_user(user_id)
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
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram notification: {e}")
