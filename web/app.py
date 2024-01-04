# web/app.py

from flask import Flask, request, jsonify
from bot.database import DatabaseManager
import os
import hashlib
import datetime
import logging
import traceback
from logging.handlers import RotatingFileHandler
from bot.freekassa_api import send_telegram_notification
from config import MERCHANT_ID, SECRET_KEY_2, FREEKASSA_IPS, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR

app = Flask(__name__)
db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

# Настройка логирования
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/yourapp.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

app.logger.setLevel(logging.INFO)
app.logger.info('YourApp startup')

def is_valid_signature(data, secret_key):
    app.logger.info(f"Validating signature with data: {data}")
    # Проверка наличия необходимых ключей
    required_keys = ['MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID']
    if not all(key in data for key in required_keys):
        return False
    
    # Формирование подписи
    generated_signature_str = f"{data['MERCHANT_ID']}:{data['AMOUNT']}:{secret_key}:{data['MERCHANT_ORDER_ID']}"
    app.logger.info(f"Generated signature string: {generated_signature_str}")
    generated_signature = hashlib.md5(generated_signature_str.encode()).hexdigest()
    app.logger.info(f"Generated signature: {generated_signature} | Received signature: {data.get('SIGN')}")

    return generated_signature == data.get('SIGN')  

def is_valid_ip(ip):
    # Проверка IP-адреса отправителя
    return ip in FREEKASSA_IPS

@app.route('/payment_webhook', methods=['POST'])
def payment_webhook():
    # Логируем заголовки и данные формы
    app.logger.info('Headers: %s', request.headers)
    app.logger.info('Form data: %s', request.form)

    # Обработка уведомлений
    data = request.form.to_dict()
    app.logger.info(f"Parsed data: {data}")

    if not is_valid_signature(data, SECRET_KEY_2):
        app.logger.error("Invalid signature. Data: {data}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Получаем данные платежа
    user_id = data.get('us_user_id')
    payment_status = data.get('int_status')  # Уточните название поля у FreeKassa

    # Проверяем наличие необходимых данных
    if user_id is None:
        app.logger.error("Missing user_id in payment data")
        return jsonify({'error': 'Missing user_id'}), 400
    if payment_status is None:
        app.logger.warning(f"Missing payment status for user_id {user_id}. Assuming payment success.")
        payment_status = "1"  # Предполагаем успешный платеж, если статус не указан

    # Handle test notifications
    if 'status_check' in request.form:
        # if is_valid_ip(request.remote_addr):
            return 'YES', 200
        # else:
            # return jsonify({'error': 'Invalid IP address'}), 403

    if data['MERCHANT_ID'] != MERCHANT_ID:
        app.logger.warning(f"Mismatched MERCHANT_ID. Expected: {MERCHANT_ID}, Received: {data['MERCHANT_ID']}")
        return jsonify({'error': 'Mismatched MERCHANT_ID'}), 400

    # Проверяем IP-адрес
    # if not is_valid_ip(request.remote_addr):
    #     app.logger.warning(f"Invalid IP: {request.remote_addr}")
    #     return jsonify({'error': 'Invalid IP address'}), 403  
    
    required_keys = ['MERCHANT_ID', 'AMOUNT', 'MERCHANT_ORDER_ID', 'SIGN']
    if not all(key in data for key in required_keys):
        missing_keys = [key for key in required_keys if key not in data]
        app.logger.warning(f"Missing required payment data fields: {missing_keys}")
        return jsonify({'error': 'Invalid payment data'}), 400

    # Получаем данные платежа
    user_id = data.get('us_user_id')  # Дополнительные параметры с префиксом us_
    payment_status = data.get('int_status', '1')  # Используем значение '1' по умолчанию, если статус не передан

    if payment_status == "1":  # Успешный платеж
        app.logger.info(f"Processing successful payment for user {user_id}")
        new_expiration_date = datetime.datetime.now() + datetime.timedelta(days=30)

        # Получение пользователя из базы данных
        user = db_manager.get_user_by_id(user_id)
        if user:
            db_manager.update_premium_status(user_id, True, new_expiration_date)
            if user.chat_id:
                send_telegram_notification(user_id, "Ваша подписка активирована! Наслаждайтесь премиум-возможностями.", db_manager)
            else:
                app.logger.error(f"Chat ID not found for user {user_id}")
        else:
            app.logger.error(f"User not found for user_id {user_id}")
    else:
        app.logger.warning(f"Payment failed or unknown status for user {user_id}")
        send_telegram_notification(user_id, "Не удалось обработать ваш платеж.", db_manager)

    # Отправляем подтверждение обработки платежа
    return 'YES', 200

@app.errorhandler(Exception)
def handle_general_error(error):
    app.logger.warning(f"An error occurred: {error}", exc_info=True)
    return jsonify(error=str(error), traceback=str(traceback.format_exc())), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)