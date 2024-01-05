
# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram.error import TimedOut
from bot.database.manager import DatabaseManager
from bot.api.hackergpt import HackerGPTAPI
from dotenv import load_dotenv
import os
import logging
import re
from bot.api.freekassa import generate_payment_link, get_chat_id_for_user, send_telegram_notification
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime
from config.settings import TELEGRAM_BOT_TOKEN, FEEDBACK_COOLDOWN, PREMIUM_SUBSCRIPTION_PRICE,ADMIN_TELEGRAM_ID, WELCOME_MESSAGE, ERROR_MESSAGE, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR, MERCHANT_ID, SECRET_KEY_1
from bot.utils.helpers import send_feedback_to_admin
from bot.commands.start import start
from bot.commands.status import status
from bot.commands.payment import handle_payment, handle_new_chat_button
from bot.common import check_message_limit, show_user_status

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Create instances for database and API interactions
db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)
hackergpt_api = HackerGPTAPI()

def update_premium_statuses():
    users = db_manager.get_all_users()
    for user in users:
        if user.premium_expiration and user.premium_expiration < datetime.now():
            db_manager.update_premium_status(user.id, False, None)

def inform_user_about_premium_status(update, context, user_id):
    if db_manager.check_premium_status(user_id):
        update.message.reply_text("У вас активна премиум подписка.")
    else:
        update.message.reply_text("У вас нет активной премиум подписки.")

def handle_tips_button(update: Update, context: CallbackContext) -> None:
    tips_text = (
        '<b>Советы по использованию чата:</b>\n\n'
        '- Вы можете задавать вопросы напрямую.\n'
        '- Ответы могут занимать некоторое время, будьте терпеливы.\n'
        '- Используйте четкие и конкретные вопросы для лучших ответов.\n'
        '- Попросите Black GPT написать план и действуйте по его пунктам.\n'
        '- Попросите Black GPT прописывать номера версий при использовании во избежание различий в методах последних версий.\n'
        '- Для решения сложной проблемы в коде - просите добавить логирование.'
    )
    update.message.reply_text(tips_text, parse_mode='HTML')

def process_feedback(user_id, feedback_text, db_manager):
    try:
        user = db_manager.get_user_by_id(user_id)
        if user:
            # Пример отправки уведомления администратору
            send_feedback_to_admin(user, feedback_text, db_manager)
            # Здесь вы также можете добавить логику для сохранения обратной связи в базу данных, если это необходимо
        else:
            logging.error(f"User with ID {user_id} not found in database.")
    except Exception as e:
        logging.error(f"Error in process_feedback: {e}")

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_message = update.message.text
    logging.info(f"Received message from user {user_id}: {user_message}")

    # Получаем данные пользователя
    user = db_manager.get_user_by_id(user_id)
    if user:
        now = datetime.now()
        # Проверяем, не слишком ли рано пользователь отправляет следующее сообщение
        if user.last_message_time and (now - user.last_message_time).total_seconds() < FEEDBACK_COOLDOWN:
            update.message.reply_text("Подождите немного, прежде чем отправлять следующее сообщение.")
            return
        # Обновляем время последнего сообщения пользователя
        user.last_message_time = now
        db_manager.session.commit()

    # Проверяем, ожидает ли бот предложения об улучшении
    if context.user_data.get('awaiting_feedback', False):
        now = datetime.now()
        if user.last_feedback_time is None or (now - user.last_feedback_time).total_seconds() > FEEDBACK_COOLDOWN:
            process_feedback(user_id, user_message, db_manager)  # Исправленный вызов
            user.last_feedback_time = now
            db_manager.session.commit()
            update.message.reply_text("Ваше предложение было отправлено администратору. Спасибо!")
        else:
            cooldown_remaining = int((FEEDBACK_COOLDOWN - (now - user.last_feedback_time).total_seconds()) / 3600)
            update.message.reply_text(f"Вы уже отправили предложение об улучшении. Следующее предложение вы сможете отправить через {cooldown_remaining} час(ов).")
        context.user_data['awaiting_feedback'] = False
        return

    # Проверяем, является ли сообщение командой для предложения улучшения
    if user_message.lower() == "предложить улучшение":
        handle_feedback_button(update, context)
        return

    # Проверка лимита сообщений для пользователя
    within_limit, remaining_messages = db_manager.is_within_message_limit(user_id)
    logging.info(f"User {user_id} has {remaining_messages} messages remaining this hour.")

    if not within_limit:
        logging.info(f"User {user_id} has reached the message limit.")
        payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
        update.message.reply_text(
            "Вы достигли лимита сообщений. Подождите час или приобретите премиум подписку.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купить премиум", url=payment_link)]
            ])
        )
    else:
        process_user_message(update, context)

def process_normal_message(update: Update, context: CallbackContext, user_id: int, user_message: str):
    # Проверка лимита сообщений перед продолжением
    within_limit, remaining_messages = db_manager.is_within_message_limit(user_id)
    logging.info(f"User {user_id} has {remaining_messages} messages remaining this hour.")

    if not within_limit:
        payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
        update.message.reply_text(
            "Вы достигли лимита сообщений. Подождите час или приобретите премиум подписку.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купить премиум", url=payment_link)]
            ])
        )
        return

    # Check if message count is initialized for this user, if not, initialize it
    if f'message_count_{user_id}' not in context.user_data:
        context.user_data[f'message_count_{user_id}'] = 0

    # Check message limit before proceeding
    if not db_manager.is_within_message_limit(user_id):
        payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
        update.message.reply_text(
            "Вы достигли лимита сообщений. Подождите час или приобретите премиум подписку.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купить премиум", url=payment_link)]
            ])
        )
        return

    # Increment message count in user data and in the database
    context.user_data[f'message_count_{user_id}'] += 1
    db_manager.update_message_count(user_id)

    try:
        process_user_message(update, context)
    except Exception as e:
        logging.error(f"Error processing message from user {user_id}: {e}")
        update.message.reply_text(ERROR_MESSAGE)

# Process user message
def process_user_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    user = update.message.from_user
    chat_id = update.message.chat.id  # Используйте chat.id вместо user.chat_id

    # Log user's message
    logging.info(f"User {user.id} ({user.username}): {user_message}")

    # Update user in database
    db_manager.add_or_update_user(user.id, user.username, user.first_name, user.last_name, chat_id)  # Используйте chat_id здесь

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

def update_message_history(context: CallbackContext, role: str, message: str) -> None:
    message_history = context.user_data.get('message_history', [])
    message_history.append({'role': role, 'content': message})
    context.user_data['message_history'] = message_history

def handle_feedback_button(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = db_manager.get_user_by_id(user_id)

    if user and db_manager.check_premium_status(user_id):
        now = datetime.now()
        if user.last_feedback_time is None or (now - user.last_feedback_time).total_seconds() > FEEDBACK_COOLDOWN:
            context.user_data['awaiting_feedback'] = True
            update.message.reply_text("Пожалуйста, напишите ваше предложение об улучшении бота.")
            user.last_feedback_time = now  # Обновляем время последнего предложения
            db_manager.session.commit()  # Сохраняем изменение в базе данных
        else:
            cooldown_remaining = int((FEEDBACK_COOLDOWN - (now - user.last_feedback_time).total_seconds()) / 3600)
            update.message.reply_text(f"Вы уже отправили предложение об улучшении. Следующее предложение вы сможете отправить через {cooldown_remaining} час(ов).")
    else:
        update.message.reply_text("Только премиум-пользователи могут отправлять предложения об улучшении.")

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

# Функция для отправки уведомлений в Telegram
def send_telegram_notification_to_admin(message, self):
    admin_chat_id = get_chat_id_for_user(ADMIN_TELEGRAM_ID, db_manager)
    if admin_chat_id:
        send_telegram_notification(ADMIN_TELEGRAM_ID, message, db_manager)
    else:
        logging.error(f"Chat ID for admin (ID: {ADMIN_TELEGRAM_ID}) not found.")

def check_expired_payment_links():
    db_manager.expire_premium_subscriptions()
    logging.info("Expired premium subscriptions have been updated.")

# Main function to set up and start the bot
def main() -> None:
    request_kwargs = {
        'read_timeout': 10,
        'connect_timeout': 10
    }
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher

    # Register command and message handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Начать новый чат$'), handle_new_chat_button))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Советы по использованию$'), handle_tips_button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Оплатить$'), handle_payment))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Предложить улучшение$'), handle_feedback_button))

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
