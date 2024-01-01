
# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram.error import TimedOut
from bot.database import DatabaseManager
from bot.hackergpt_api import HackerGPTAPI
from dotenv import load_dotenv
from os import getenv
import os
import logging
import re
from .freekassa_api import generate_payment_link
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load environment variables explicitly
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Get tokens from environment variables
# Получение переменных окружения
FREEKASSA_API_KEY = getenv('FREEKASSA_API_KEY')
MERCHANT_ID = getenv('FREEKASSA_MERCHANT_ID')
SECRET_KEY_1 = getenv('SECRET_KEY_1')
SECRET_KEY_2 = getenv('SECRET_KEY_2')
TELEGRAM_TOKEN = getenv('TELEGRAM_TOKEN')
WELCOME_MESSAGE = 'Привет! Я BlackGPT бот. Задайте мне вопрос.'
ERROR_MESSAGE = 'Извините, возникла проблема при обработке вашего запроса.'
PREMIUM_SUBSCRIPTION_PRICE = 50  # Примерная сумма оплаты за премиум подписку

# Create instances for database and API interactions
db_manager = DatabaseManager()
hackergpt_api = HackerGPTAPI()

def update_premium_statuses():
    users = db_manager.get_all_users()
    for user in users:
        if user.premium_expiration_date and user.premium_expiration_date < datetime.now():
            db_manager.update_premium_status(user.id, False, None)

def handle_payment(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
    update.message.reply_text(
        "Для приобретения премиум подписки перейдите по ссылке:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Оплатить", url=payment_link)]
        ])
    )

def check_message_limit(user_id, context):
    user_message_count = context.user_data.get(f'message_count_{user_id}', 0)
    if user_message_count >= 1:  # Замените 1 на соответствующий лимит
        payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1)
        return True, payment_link
    return False, None

def inform_user_about_premium_status(update, context, user_id):
    if db_manager.check_premium_status(user_id):
        update.message.reply_text("У вас активна премиум подписка.")
    else:
        update.message.reply_text("У вас нет активной премиум подписки.")

# Command handler for /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(WELCOME_MESSAGE, reply_markup=get_base_reply_markup())

def handle_tips_button(update: Update, context: CallbackContext) -> None:
    tips_text = (
        '<b>Советы по использованию чата:</b>\n'
        '- Вы можете задавать вопросы напрямую.\n'
        '- Ответы могут занимать некоторое время, будьте терпеливы.\n'
        '- Используйте четкие и конкретные вопросы для лучших ответов.\n'
        '- Попросите Black GPT написать план и действуйте по его пунктам.\n'
        '- Попросите Black GPT прописывать номера версий при использовании во избежание различий в методах последних версий.\n'
        '- Для решения сложной проблемы в коде - просите добавить логирование.'
    )
    update.message.reply_text(tips_text, parse_mode='HTML')

def handle_new_chat_button(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if db_manager.check_premium_status(user_id):
        context.user_data[f'message_count_{user_id}'] = 0
        update.message.reply_text("Новый чат начат с премиум доступом!")
    else:
        # Проверка лимита сообщений
        limit_reached, payment_link = check_message_limit(user_id, context)
        if limit_reached:
            update.message.reply_text(
                "Вы достигли лимита сообщений. Приобретите премиум подписку для продолжения.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )
        else:
            context.user_data[f'message_count_{user_id}'] = 0
            update.message.reply_text("Новый чат начат!")

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Handling message from user {user_id}")

    # Initialize message count if it doesn't exist
    if f'message_count_{user_id}' not in context.user_data:
        context.user_data[f'message_count_{user_id}'] = 0

    limit_reached, payment_link = check_message_limit(user_id, context)
    if limit_reached:
        update.message.reply_text(
            "Вы достигли лимита сообщений. Приобретите премиум подписку для продолжения.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купить премиум", url=payment_link)]
            ])
        )
        return
    # Увеличиваем счетчик сообщений
    context.user_data[f'message_count_{user_id}'] += 1
    try:
        process_user_message(update, context)
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        update.message.reply_text("Произошла ошибка при связи с нашим сервером. Пожалуйста, попробуйте позже.")

# Process user message
def process_user_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    user = update.message.from_user

    # Log user's message
    logging.info(f"User {user.id} ({user.username}): {user_message}")

    # Update user in database
    db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name)

    # Update message history
    update_message_history(context, 'user', user_message)

    # Send temporary "Generating response..." message
    temp_message = update.message.reply_text("Генерирую ответ...")

    # Get response from API
    response_text = hackergpt_api.send_message(context.user_data['message_history'])

    # Log GPT's response
    logging.info(f"GPT response to {user.id} ({user.username}): {response_text}")

    # Format code blocks in the response
    formatted_response_text = format_code_block(response_text)

    # Escape Markdown V2 special characters
    escaped_response_text = escape_markdown_v2(formatted_response_text)

    # Record query and response in the database
    db_manager.add_query(user.id, user_message, escaped_response_text)

    # Edit the temporary message with the actual response
    context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=temp_message.message_id,
        text=escaped_response_text,
        parse_mode='MarkdownV2'
    )

# Вспомогательные функции
def get_base_reply_markup():
    new_chat_button = KeyboardButton('Начать новый чат')
    tips_button = KeyboardButton('Советы по использованию')
    return ReplyKeyboardMarkup([[new_chat_button], [tips_button]], resize_keyboard=True, one_time_keyboard=False)

def update_message_history(context: CallbackContext, role: str, message: str) -> None:
    message_history = context.user_data.get('message_history', [])
    message_history.append({'role': role, 'content': message})
    context.user_data['message_history'] = message_history

def escape_markdown_v2(text):
    # Escape Markdown V2 special characters outside of code blocks
    escape_chars = '_*[]()~`>#+-=|{}.!'
    # Split the text into code blocks and the rest
    parts = re.split(r'(```.*?```)', text, flags=re.DOTALL)
    escaped_parts = []
    for part in parts:
        if part.startswith('```') and part.endswith('```'):
            # Don't escape characters inside code blocks
            escaped_parts.append(part)
        else:
            # Escape special characters outside code blocks
            escaped_parts.append(re.sub(r'([_*\[\]()~`>#\+=\-|{}\.!])', r'\\\1', part))
    return ''.join(escaped_parts)

def format_code_block(response_text):
    # Find code blocks with language hints and replace them without language hints
    pattern = r'```(\w+)?\s*(.+?)\s*```'
    formatted_text = re.sub(pattern, r'```\n\2\n```', response_text, flags=re.DOTALL)
    return formatted_text

def check_expired_payment_links():
    db_manager.expire_premium_subscriptions()
    logging.info("Expired premium subscriptions have been updated.")

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
    dispatcher.add_handler(MessageHandler(Filters.regex('^Советы по использованию$'), handle_tips_button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Оплатить$'), handle_payment))

    scheduler = BackgroundScheduler(timezone=pytz.utc)
    scheduler.add_job(update_premium_statuses, 'interval', hours=24)
    scheduler.add_job(check_expired_payment_links, 'interval', hours=24)
    scheduler.start()

    # Start the bot
    updater.start_polling()
    updater.idle()

# Program entry point
if __name__ == '__main__':
    main()
