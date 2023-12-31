# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram.error import TimedOut
from bot.database import DatabaseManager
from bot.hackergpt_api import HackerGPTAPI
from dotenv import load_dotenv
from os import getenv, path
import os

# Явно указываем путь к файлу .env
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Получение токенов из переменных окружения
TELEGRAM_TOKEN = getenv('TELEGRAM_TOKEN')
WELCOME_MESSAGE = 'Привет! Я BlackGPT бот. Задайте мне вопрос.'
ERROR_MESSAGE = 'Извините, возникла проблема при обработке вашего запроса.'

# Создание экземпляров классов для работы с базой данных и API
db_manager = DatabaseManager()
hackergpt_api = HackerGPTAPI()

# Функция для создания клавиатуры
def get_base_reply_markup():
    button = KeyboardButton('Начать новый чат')
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(WELCOME_MESSAGE, reply_markup=get_base_reply_markup())

# Обработчик нажатия на кнопку "Начать новый чат"
def handle_new_chat_button(update: Update, context: CallbackContext) -> None:
    # Сброс истории сообщений пользователя
    context.user_data['message_history'] = []
    update.message.reply_text("Новый чат начат!")

# Обработчик текстовых сообщений
def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    user = update.message.from_user

    # Добавление или обновление пользователя в базе данных
    db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)

    # Создание или обновление истории сообщений пользователя
    message_history = context.user_data.get('message_history', [])
    message_history.append({'role': 'user', 'content': user_message})

    # Получение ответа от API BlackGPT
    try:
        response_text = hackergpt_api.send_message(message_history)
        message_history.append({'role': 'assistant', 'content': response_text})

        # Запись запроса и ответа в базу данных
        db_manager.add_query(user.id, user_message, response_text)

        # Отправка текста ответа пользователю
        update.message.reply_text(response_text)

    except TimedOut as e:
        # Обработка ошибки таймаута
        print(f"Ошибка таймаута при отправке сообщения: {e}")
        update.message.reply_text("Произошла ошибка сети, пожалуйста, попробуйте еще раз.")
    except Exception as e:
        # Обработка других исключений
        print(f"Ошибка при запросе к API BlackGPT: {e}")
        update.message.reply_text(ERROR_MESSAGE)

    # Обновление истории сообщений в контексте пользователя
    context.user_data['message_history'] = message_history

# Главная функция для настройки и запуска бота
def main() -> None:
    request_kwargs = {
        'read_timeout': 10,  # Увеличьте read_timeout, если необходимо
        'connect_timeout': 10  # Увеличьте connect_timeout, если необходимо
    }
    updater = Updater(TELEGRAM_TOKEN, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков команд и сообщений
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Начать новый чат$'), handle_new_chat_button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск бота
    updater.start_polling()
    updater.idle()

# Точка входа в программу
if __name__ == '__main__':
    main()