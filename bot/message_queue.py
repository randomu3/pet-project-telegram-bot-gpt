# bot/message_queue.py

import logging
import pika
import json

class MessageQueue:
    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue_name)

    def send_message(self, message):
        try:
            self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=json.dumps(message))
            logging.info(f"Message sent to queue {self.queue_name}: {message}")
        except Exception as e:
            logging.error(f"Error sending message to queue {self.queue_name}: {e}")

    def __del__(self):
        self.connection.close()

# В main.py добавьте создание экземпляра MessageQueue
mq = MessageQueue('telegram_broadcast')