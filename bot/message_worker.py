# message_worker.py

import logging
import pika
import json
from bot.freekassa_api import send_telegram_notification
from bot.database import DatabaseManager

class MessageConsumer:
    def __init__(self, queue_name, db_manager, prefetch_count=1):  # Добавьте параметр с значением по умолчанию
        self.queue_name = queue_name
        self.db_manager = db_manager
        self.prefetch_count = prefetch_count  # Сохраните значение в атрибуте класса
        
        # Установите соединение с RabbitMQ
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.basic_qos(prefetch_count=self.prefetch_count)  # Установите значение prefetch_count для канала

    def start_consuming(self):
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_message, auto_ack=True)
        self.channel.start_consuming()

    def on_message(self, ch, method, properties, body):
        logging.info(f"Received message from queue {self.queue_name}: {body}")
        try:
            message_data = json.loads(body)
            user_id = message_data['user_id']
            message = message_data['message']
            send_telegram_notification(user_id, message, self.db_manager)
            logging.info(f"Message processed for user {user_id}: {message}")
        except Exception as e:
            logging.error(f"Error processing message from queue {self.queue_name}: {e}")

    def __del__(self):
        self.connection.close()

if __name__ == "__main__":
    consumer = MessageConsumer('telegram_broadcast', db_manager)
    consumer.start_consuming()