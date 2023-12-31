# bot/api/freekassa.py

import hashlib
from datetime import datetime
import logging
import requests
import os
from config.settings import TELEGRAM_BOT_TOKEN, MERCHANT_ID, SECRET_KEY_1

def generate_payment_link(user_id, amount, merchant_id=MERCHANT_ID, SECRET_KEY_1=SECRET_KEY_1, currency="RUB", lang="ru"):
    order_id = str(int(datetime.now().timestamp()))

    # Формирование строки подписи
    sign_str = f"{merchant_id}:{amount}:{SECRET_KEY_1}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    # Формирование URL
    payment_url = f"https://pay.kassa.shop/?m={merchant_id}&oa={amount}&o={order_id}&currency={currency}&s={sign}&lang={lang}&us_user_id={user_id}&strd=1"
    return payment_url

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
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram notification: {e}")
