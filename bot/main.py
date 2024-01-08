
# bot/main.py

import threading
from bot.message_queue import MessageQueue
from bot.message_worker import MessageConsumer
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from bot.database import DatabaseManager
from bot.hackergpt_api import HackerGPTAPI
from dotenv import load_dotenv
import logging
import re
from bot.freekassa_api import get_chat_id_for_user, send_telegram_notification
from bot.utils import generate_payment_link
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime, timedelta
from config import TELEGRAM_BOT_TOKEN, FEEDBACK_COOLDOWN, PREMIUM_SUBSCRIPTION_PRICE,ADMIN_TELEGRAM_ID, WELCOME_MESSAGE, ERROR_MESSAGE, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR, MERCHANT_ID, SECRET_KEY_1
from bot.telegram_utils import send_feedback_to_admin

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Create instances for database and API interactions
db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)
hackergpt_api = HackerGPTAPI()

# Глобальная инициализация MessageQueue
mq = MessageQueue('telegram_broadcast')

def update_premium_statuses():
    users = db_manager.get_all_users()
    for user in users:
        if user.premium_expiration and user.premium_expiration < datetime.now():
            db_manager.update_premium_status(user.id, False, None)

def handle_payment(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    # Проверяем, актуальна ли ссылка на оплату
    if not db_manager.is_payment_link_valid(user_id):
        update.message.reply_text("Ссылка для оплаты истекла. Пожалуйста, запросите новую.")
        return

    # Если ссылка актуальна, продолжаем процесс оплаты
    payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, db_manager)
    update.message.reply_text(
        "Для приобретения премиум подписки перейдите по ссылке:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Оплатить", url=payment_link)]
        ])
    )

def check_message_limit (user_id, context, db_manager):
    user = db_manager.get_user_by_id(user_id)
    if user:
        limit = MAX_QUESTIONS_PER_HOUR_PREMIUM if user.is_premium else MAX_QUESTIONS_PER_HOUR_REGULAR
        logging.info(f"Checking message limit for user {user_id}. Premium: {user.is_premium}, Message count: {user.message_count}, Limit: {limit}")
        return user.message_count >= limit
    else:
        logging.warning(f"User {user_id} not found when checking message limit.")
        return False  # If the user is not found, do not allow sending messages by default

def inform_user_about_premium_status(update, context, user_id):
    if db_manager.check_premium_status(user_id):
        update.message.reply_text("У вас активна премиум подписка.")
    else:
        update.message.reply_text("У вас нет активной премиум подписки.")

def status(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = db_manager.get_user_by_id(user_id)

    if user:
        is_premium = user.is_premium
        premium_status_message = "У вас активна премиум подписка." if is_premium else "У вас нет активной премиум подписки."

        if is_premium and user.premium_expiration:
            expiration_date = user.premium_expiration.strftime("%Y-%m-%d %H:%M:%S")
            premium_status_message += f"\n- Действительна до {expiration_date}."

        # Выводим оставшееся количество вопросов для всех пользователей
        message_limit = MAX_QUESTIONS_PER_HOUR_PREMIUM if is_premium else MAX_QUESTIONS_PER_HOUR_REGULAR
        remaining_questions = message_limit - user.message_count
        remaining_questions_message = f"- Вопросов осталось: {remaining_questions} в этот час"

        status_msg = f"📌 Ваш статус:\n- {premium_status_message}\n{remaining_questions_message}"
        update.message.reply_text(status_msg)
    else:
        update.message.reply_text("Ошибка: информация о пользователе не найдена.")

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
    premium_status_message = "У вас активна премиум подписка." if is_premium else f"У вас нет активной премиум подписки.\nВам доступно {MAX_QUESTIONS_PER_HOUR_REGULAR} запроса."

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
        '- Сделайте запрос Black GPT, написать план и действуйте по его пунктам.\n'
        '- Сделайте запрос Black GPT, прописывать номера версий при использовании во избежание различий в методах последних версий.\n'
        '- Для решения сложной проблемы в коде - просите добавить логирование.'
    )
    update.message.reply_text(tips_text, parse_mode='HTML')

def handle_new_chat_button(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Логирование нажатия кнопки нового чата
    logging.info(f"User {user_id} clicked 'New Chat' button")
    
    # Очистка истории сообщений
    message_history = context.user_data.get('message_history', [])
    for message in message_history:
        db_manager.add_message_history(user_id, message['content'])

    # Очищаем историю сообщений
    context.user_data['message_history'] = []

    if db_manager.check_premium_status(user_id):
        context.user_data[f'message_count_{user_id}'] = 0
        db_manager.update_message_count(user_id)  # Обнуляем счетчик сообщений в базе данных
        update.message.reply_text("Новый чат начат с премиум доступом!")
    else:
        # Проверка лимита сообщений
        limit_reached = check_message_limit(user_id, context, db_manager)
        if limit_reached:
            next_message_time = db_manager.get_next_message_time(user_id)
            next_message_time_str = next_message_time.strftime("%Y-%m-%d %H:%M:%S") if next_message_time else "скоро"
            payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, db_manager, MERCHANT_ID, SECRET_KEY_1)
            update.message.reply_text(
                f"Вы достигли лимита сообщений. Время, когда вы сможете написать следующий вопрос BlackGPT - {next_message_time_str}.\n\n"
                "Приобретите премиум подписку и получите более высокие лимиты.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )
        else:
            context.user_data[f'message_count_{user_id}'] = 0
            update.message.reply_text("Новый чат начат!")
            # Добавляем сообщение о возможности покупки премиума
            payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, db_manager, MERCHANT_ID, SECRET_KEY_1)
            update.message.reply_text(
                "Приобретите премиум подписку, чтобы не ограничивать себя в сообщениях и получить дополнительные преимущества.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )

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

    # Проверяем, находится ли администратор в режиме рассылки
    if context.user_data.get('is_broadcasting', False) and str(user_id) == ADMIN_TELEGRAM_ID:
        broadcast_to_all_users(user_message, db_manager)
        context.user_data['is_broadcasting'] = False
        update.message.reply_text("Сообщение отправлено всем пользователям.")
        return

    # Получаем данные пользователя
    user = db_manager.get_user_by_id(user_id)
    if user:
        now = datetime.now()

        # Если время последнего сообщения не установлено, устанавливаем текущее время
        if user.last_message_time is None:
            user.last_message_time = now

        # Сброс счетчика, если прошел час с момента последнего сообщения
        if (now - user.last_message_time).total_seconds() >= 3600:
            user.message_count = 0
            user.last_message_time = now

        # Обновляем счетчик сообщений
        user.message_count += 1
        db_manager.session.commit()

        # Логирование текущего состояния счетчика
        logging.info(f"User {user_id} message count updated to: {user.message_count}")

        # Логируем текущее количество сообщений и оставшееся время до сброса счетчика
        if user.message_count is not None:
            time_until_reset = 3600 - (now - user.last_message_time).total_seconds()
            logging.info(f"User {user_id} message count: {user.message_count}. Time until reset: {time_until_reset} seconds")

    # Log current message count
    logging.info(f"User {user_id} message count before processing: {user.message_count if user else 'User not found'}")

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
    logging.info(f"User {user_id} has {remaining_messages} messages remaining this hour. Within limit: {within_limit}")

    if not within_limit:
        # Если лимит сообщений исчерпан
        inform_limit_reached(update, user_id)  # Функция для информирования пользователя о достижении лимита
    else:
        # Если лимит не исчерпан
        process_user_message(update, context)
        # Обновляем счетчик сообщений
        db_manager.update_message_count(user_id)
        logging.info(f"After updating, User {user_id} has {remaining_messages - 1} messages remaining this hour.")

def inform_limit_reached(update, user_id):
    user = db_manager.get_user_by_id(user_id)
    if user and user.last_message_time:
        next_message_time = user.last_message_time + timedelta(seconds=3600)
        next_message_time_str = next_message_time.strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"Вы достигли лимита сообщений в час. Время, когда вы сможете написать следующий вопрос BlackGPT - {next_message_time_str}. \n\n"
            "Приобретите премиум подписку и получите более высокие лимиты."
        )
    else:
        message = "Произошла ошибка при определении времени следующего сообщения. Напишите команду /start"

    payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, db_manager)  # Исправлен вызов функции
    update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Купить премиум", url=payment_link)]
        ])
    )
    
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

# Вспомогательные функции
def get_base_reply_markup():
    new_chat_button = KeyboardButton('Начать новый чат')
    tips_button = KeyboardButton('Советы по использованию')
    feedback_button = KeyboardButton('Предложить улучшение')
    return ReplyKeyboardMarkup([[new_chat_button], [tips_button], [feedback_button]], resize_keyboard=True, one_time_keyboard=False)

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

# Добавьте новый обработчик команды
def broadcast_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Broadcast command triggered by user {user_id}")
    
    if str(user_id) != ADMIN_TELEGRAM_ID:
        logging.warning(f"Unauthorized attempt to use broadcast command by user {user_id}")
        update.message.reply_text("У вас нет прав для использования этой команды.")
        return

    context.user_data['is_broadcasting'] = True
    update.message.reply_text("Введите сообщение для рассылки всем пользователям:")

def broadcast_to_all_users(message, db_manager):
    # Добавляем префикс к сообщению
    # prefixed_message = f"Сообщение от администратора: {message}"
    # send_telegram_notification(user.id, prefixed_message, db_manager)
    users = db_manager.get_all_users()
    for user in users:
        mq.send_message({'user_id': user.id, 'message': message})

def grant_premium_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if str(user_id) != ADMIN_TELEGRAM_ID:
        update.message.reply_text("У вас нет прав для использования этой команды.")
        return

    try:
        target_user_id = int(context.args[0])
        new_expiration_date = datetime.now() + timedelta(days=30)
        db_manager.update_premium_status(target_user_id, True, new_expiration_date)
        update.message.reply_text(f"Премиум доступ выдан пользователю с ID {target_user_id} на месяц.")
        send_telegram_notification(target_user_id, "Вам выдан премиум доступ на месяц!", db_manager)
    except (IndexError, ValueError):
        update.message.reply_text("Пожалуйста, укажите корректный ID пользователя.")

# Main function to set up and start the bot
def main() -> None:
    request_kwargs = {
        'read_timeout': 10,
        'connect_timeout': 10
    }
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher

     # Создание экземпляра DatabaseManager
    db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

    # Register command and message handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast_command))
    dispatcher.add_handler(CommandHandler("grantpremium", grant_premium_command))

    dispatcher.add_handler(MessageHandler(Filters.regex('^Начать новый чат$'), handle_new_chat_button))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Советы по использованию$'), handle_tips_button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Оплатить$'), handle_payment))
    dispatcher.add_handler(MessageHandler(Filters.regex('^Предложить улучшение$'), handle_feedback_button))

    scheduler = BackgroundScheduler(timezone=pytz.utc)
    scheduler.add_job(update_premium_statuses, 'interval', hours=24)
    scheduler.add_job(check_expired_payment_links, 'interval', hours=24)
    scheduler.add_job(db_manager.expire_payment_links, 'interval', hours=24)
    scheduler.start()

    # Создаем экземпляр MessageConsumer с указанным значением prefetch_count
    consumer = MessageConsumer('telegram_broadcast', db_manager, prefetch_count=4)
    consumer_thread = threading.Thread(target=consumer.start_consuming)
    consumer_thread.start()

    # Start the bot
    updater.start_polling()
    updater.idle()

# Program entry point
if __name__ == '__main__':
    main()
