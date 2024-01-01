# web/app.py

from flask import Flask, request, jsonify
from bot.database import DatabaseManager
import os
import hashlib
import datetime
import logging
import traceback
from bot.freekassa_api import send_telegram_notification

app = Flask(__name__)
db_manager = DatabaseManager()

MERCHANT_ID = os.getenv('FREEKASSA_MERCHANT_ID')
SECRET_KEY_2 = os.getenv('FREEKASSA_SECRET_KEY_2')  # Используйте "Секретное слово 2" для подписи вебхука

FREEKASSA_IPS = ['168.119.157.136', '168.119.60.227', '138.201.88.124', '178.154.197.79']

def is_valid_signature(data, secret_key):
    print(f"Debug Signature Data: MERCHANT_ID={data.get('MERCHANT_ID')}, AMOUNT={data.get('AMOUNT')}, SECRET_KEY_2={secret_key}, MERCHANT_ORDER_ID={data.get('MERCHANT_ORDER_ID')}")
    # Проверка наличия необходимых ключей
    required_keys = ['MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID']
    if not all(key in data for key in required_keys):
        return False
    generated_signature = hashlib.md5(f"{data['MERCHANT_ID']}:{data['AMOUNT']}:{secret_key}:{data['MERCHANT_ORDER_ID']}".encode()).hexdigest()
    return generated_signature == data.get('SIGN')

def is_valid_ip(ip):
    # Проверка IP-адреса отправителя
    return ip in FREEKASSA_IPS

@app.route('/payment_webhook', methods=['POST'])
def payment_webhook():
    logging.info(f"Request IP: {request.remote_addr}")
    # Handle test notifications
    if 'status_check' in request.form:
        # if is_valid_ip(request.remote_addr):
            return 'YES', 200
        # else:
            # return jsonify({'error': 'Invalid IP address'}), 403

    # Ensure real notifications contain all necessary fields
    data = request.form.to_dict()
    required_keys = ['MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID', 'SIGN']
    if not all(key in data for key in required_keys):
        logging.error("Missing required payment data fields.")
        return jsonify({'error': 'Invalid payment data'}), 400

    # Validate signature for real notifications
    if not is_valid_signature(data, SECRET_KEY_2):
        logging.error("Invalid signature.")
        return jsonify({'error': 'Invalid signature'}), 400

    # Получаем данные платежа
    user_id = data.get('us_user_id')  # Дополнительные параметры с префиксом us_
    payment_status = data.get('int_status')  # Нет такого поля в документации, но предположим, что это статус

    # Проверяем наличие необходимых данных
    if user_id is None or payment_status is None:
        return jsonify({'error': 'Missing user_id or status'}), 400

    # Обработка статуса платежа
    if payment_status == "1":  # Предполагаем, что '1' означает успешный платеж
        new_expiration_date = datetime.datetime.now() + datetime.timedelta(days=30)
        db_manager.update_premium_status(user_id, True, new_expiration_date)
        send_telegram_notification(user_id, "Ваша подписка активирована! Наслаждайтесь премиум-возможностями.")
    else:
        send_telegram_notification(user_id, "Не удалось обработать ваш платеж.")

    # Отправляем подтверждение обработки платежа
    return 'YES', 200

@app.errorhandler(Exception)
def handle_general_error(error):
    logging.error(f"An error occurred: {error}")
    return jsonify(error=str(error), traceback=str(traceback.format_exc())), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)