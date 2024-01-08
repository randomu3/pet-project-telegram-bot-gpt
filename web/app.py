# web/app.py

from config import MERCHANT_ID, SECRET_KEY_2, FREEKASSA_IPS, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR, moscow_tz
from bot.freekassa_api import send_telegram_notification
from bot.database import DatabaseManager, PaymentLink
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
import traceback
from datetime import datetime as dt
from datetime import datetime, timedelta
import logging
import hashlib
import os

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
    # Формирование подписи
    string_to_sign = f"{data['MERCHANT_ID']}:{data['AMOUNT']}:{secret_key}:{data['MERCHANT_ORDER_ID']}"
    generated_signature = hashlib.md5(string_to_sign.encode()).hexdigest()
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

    # Обработка запроса проверки статуса от FreeKassa
    if 'status_check' in data:
        app.logger.info("Status check request received")
        return 'YES', 200

    # Проверка подписи
    if not is_valid_signature(data, SECRET_KEY_2):
        app.logger.error("Invalid signature")
        return 'Invalid signature', 400
    
    # Проверка статуса платежа
    if not data.get('intid'):
        app.logger.warning(f"Payment failed or unknown status for user {data.get('us_user_id')}")
        return 'NO', 400

    # Поиск платежной ссылки в базе данных
    order_id = data.get('MERCHANT_ORDER_ID')
    payment_link = db_manager.session.query(PaymentLink).filter(PaymentLink.order_id == order_id).first()

    # Добавим проверку на наличие payment_link и проверим, что дата истечения не является "наивной"
    if payment_link and payment_link.expiration_time and payment_link.expiration_time.tzinfo is None:
        payment_link.expiration_time = moscow_tz.localize(payment_link.expiration_time)

    if not payment_link or payment_link.expiration_time < datetime.now(moscow_tz):
        app.logger.error("Invalid or expired payment link.")
        user_id = data.get('us_user_id')
        send_telegram_notification(user_id, "Ваша попытка оплаты не удалась, так как ссылка для оплаты истекла.", db_manager)
        return 'NO', 400

    if payment_link.is_paid:
        app.logger.warning("This payment has already been processed.")
        return 'NO', 400

    payment_link.is_paid = True
    db_manager.session.commit()

    # Обновление статуса пользователя
    user_id = data.get('us_user_id')
    new_expiration_date = datetime.now(moscow_tz) + timedelta(days=30)
    db_manager.update_premium_status(user_id, True, new_expiration_date)
    db_manager.reset_message_count(user_id)
    send_telegram_notification(user_id, "Ваша подписка активирована! Наслаждайтесь премиум-возможностями.", db_manager)

    return 'YES', 200

@app.errorhandler(Exception)
def handle_general_error(error):
    app.logger.warning(f"An error occurred: {error}", exc_info=True)
    return jsonify(error=str(error), traceback=str(traceback.format_exc())), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)