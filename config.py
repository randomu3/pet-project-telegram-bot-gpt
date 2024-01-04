# config.py
from dotenv import load_dotenv
from os import getenv
import os

# Load environment variables explicitly
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Настройки базы данных
DATABASE_URL = "sqlite:///bot_database.db"

# Токены и ключи API
FREEKASSA_API_KEY = getenv('FREEKASSA_API_KEY')
MERCHANT_ID = getenv('FREEKASSA_MERCHANT_ID')
SECRET_KEY_1 = getenv('FREEKASSA_SECRET_KEY_1')
SECRET_KEY_2 = getenv('FREEKASSA_SECRET_KEY_2')
TELEGRAM_BOT_TOKEN = getenv('TELEGRAM_BOT_TOKEN')
HACKERGPT_API_KEY = getenv('HACKERGPT_API_KEY')
HACKERGPT_LINK = getenv('HACKERGPT_LINK')

# Настройки приложения и сообщений
WELCOME_MESSAGE = "Привет! Я BlackGPT бот. Задайте мне вопрос."
ERROR_MESSAGE = "Извините, возникла проблема при обработке вашего запроса."
PREMIUM_SUBSCRIPTION_PRICE = 10

# Константы для управления лимитами сообщений
MAX_QUESTIONS_PER_HOUR_PREMIUM = 10
MAX_QUESTIONS_PER_HOUR_REGULAR = 1

# Дополнительные настройки
FREEKASSA_IPS = ['168.119.157.136', '168.119.60.227', '138.201.88.124', '178.154.197.79']

# Настройки логирования
LOG_FILE = 'logs/yourapp.log'
LOG_MAX_BYTES = 10240
LOG_BACKUP_COUNT = 10
