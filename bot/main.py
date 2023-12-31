
# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram.error import TimedOut
from bot.database import DatabaseManager
from bot.hackergpt_api import HackerGPTAPI
from dotenv import load_dotenv
from os import getenv, path
import os
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load environment variables explicitly
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Get tokens from environment variables
TELEGRAM_TOKEN = getenv('TELEGRAM_TOKEN')
WELCOME_MESSAGE = 'Привет! Я BlackGPT бот. Задайте мне вопрос.'
ERROR_MESSAGE = 'Извините, возникла проблема при обработке вашего запроса.'

# Create instances for database and API interactions
db_manager = DatabaseManager()
hackergpt_api = HackerGPTAPI()

# Function to create a keyboard
def get_base_reply_markup():
    button = KeyboardButton('Начать новый чат')
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

# Command handler for /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(WELCOME_MESSAGE, reply_markup=get_base_reply_markup())

# Handler for "Начать новый чат" button
def handle_new_chat_button(update: Update, context: CallbackContext) -> None:
    context.user_data['message_history'] = []
    update.message.reply_text("Новый чат начат!")

# Handler for text messages
def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        process_user_message(update, context)
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        update.message.reply_text("Произошла ошибка при связи с нашим сервером. Пожалуйста, попробуйте позже.")

# Process user message
def process_user_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    user = update.message.from_user

    # Update user in database
    db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)

    # Update message history
    update_message_history(context, 'user', user_message)

    # Get response from API
    response_text = hackergpt_api.send_message(context.user_data['message_history'])
    update_message_history(context, 'assistant', response_text)

    # Record query and response in database
    db_manager.add_query(user.id, user_message, response_text)

    # Send response to user
    update.message.reply_text(response_text)

# Update message history
def update_message_history(context: CallbackContext, role: str, message: str) -> None:
    message_history = context.user_data.get('message_history', [])
    message_history.append({'role': role, 'content': message})
    context.user_data['message_history'] = message_history

# Main function to set up and start the bot
def main() -> None:
    request_kwargs = {
        'read_timeout': 10,
        'connect_timeout': 10
    }
    updater = Updater(TELEGRAM_TOKEN, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher

    # Register command and message handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Начать новый чат$'), handle_new_chat_button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the bot
    updater.start_polling()
    updater.idle()

# Program entry point
if __name__ == '__main__':
    main()
