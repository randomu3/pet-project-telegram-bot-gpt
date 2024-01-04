
# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram.error import TimedOut
from bot.database import DatabaseManager
from bot.hackergpt_api import HackerGPTAPI
from dotenv import load_dotenv
import os
import logging
import re
from .freekassa_api import generate_payment_link
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, PREMIUM_SUBSCRIPTION_PRICE, WELCOME_MESSAGE, ERROR_MESSAGE, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR, MERCHANT_ID, SECRET_KEY_1

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

def handle_payment(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
    update.message.reply_text(
        "Для приобретения премиум подписки перейдите по ссылке:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Оплатить", url=payment_link)]
        ])
    )

def check_message_limit(user_id, context, db_manager):
    user_message_count = context.user_data.get(f'message_count_{user_id}', 0)
    if db_manager.check_premium_status(user_id):
        return user_message_count >= 10  # Лимит для премиум-пользователей
    else:
        return user_message_count >= 1  # Лимит для обычных пользователей

def inform_user_about_premium_status(update, context, user_id):
    if db_manager.check_premium_status(user_id):
        update.message.reply_text("У вас активна премиум подписка.")
    else:
        update.message.reply_text("У вас нет активной премиум подписки.")

def status(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    show_user_status(update, context, user_id)

# Command handler for /start
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_name = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    chat_id = update.message.chat.id

    # Проверяем, существует ли пользователь в базе данных
    if not db_manager.get_user_by_id(user_id):
        db_manager.add_or_update_user(user_id, user_name, first_name, last_name, chat_id)

    # Проверяем, есть ли у пользователя премиум-статус
    is_premium = db_manager.check_premium_status(user_id)
    premium_status_message = "У вас активна премиум подписка." if is_premium else "У вас нет активной премиум подписки."

    # Информация о премиум подписке
    premium_info = (
        f"🌟 <b>Премиум Подписка:</b>\n"
        f"- Стоимость: {PREMIUM_SUBSCRIPTION_PRICE} рублей в месяц.\n"
        f"- Срок действия: 1 месяц.\n"
        f"- Преимущества: {MAX_QUESTIONS_PER_HOUR_PREMIUM} сообщений в час.\n\n"
        f"{premium_status_message}"
    )

    # Отправляем приветственное сообщение с информацией о премиум подписке
    update.message.reply_text(f"{WELCOME_MESSAGE}\n\n{premium_info}", reply_markup=get_base_reply_markup(), parse_mode='HTML')

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
        db_manager.update_message_count(user_id)  # Обнуляем счетчик сообщений в базе данных
        update.message.reply_text("Новый чат начат с премиум доступом!")
    else:
        # Проверка лимита сообщений
        limit_reached = check_message_limit(user_id, context, db_manager)
        if limit_reached:
            payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1)
            update.message.reply_text(
                "Вы достигли лимита сообщений. Приобретите премиум подписку для продолжения.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )
        else:
            context.user_data[f'message_count_{user_id}'] = 0
            update.message.reply_text("Новый чат начат!")
            # Добавляем сообщение о возможности покупки премиума
            payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1)
            update.message.reply_text(
                "Приобретите премиум подписку, чтобы не ограничивать себя в сообщениях и получить дополнительные преимущества.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

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

def show_user_status(update, context, user_id):
    try:
        user = db_manager.get_user_by_id(user_id)
        if user:
            remaining_questions = (MAX_QUESTIONS_PER_HOUR_PREMIUM if user.is_premium else MAX_QUESTIONS_PER_HOUR_REGULAR) - user.message_count
            status_msg = f"📌 Условия использования:\n- Вопросов осталось: {remaining_questions} в этот час\n- Премиум статус: {'Активен' if user.is_premium else 'Не активен'}"
            update.message.reply_text(status_msg)
    except Exception as e:
        logging.error(f"Error in show_user_status: {e}")
        update.message.reply_text("Произошла ошибка при отображении статуса.")

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
