
# bot/main.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CallbackContext, Filters, CallbackQueryHandler
from telegram.error import TimedOut
from bot.database.manager import DatabaseManager
from bot.api.hackergpt import HackerGPTAPI
import logging
from bot.api.freekassa import generate_payment_link, get_chat_id_for_user, send_telegram_notification
from datetime import datetime
from config.settings import TELEGRAM_BOT_TOKEN, FEEDBACK_COOLDOWN, PREMIUM_SUBSCRIPTION_PRICE,ADMIN_TELEGRAM_ID, ERROR_MESSAGE, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR
from bot.utils.helpers import process_user_message, process_feedback
from bot.handlers import command_handlers, message_handlers
from bot.scheduler import scheduler_tasks
from bot.handlers.button_handlers import handle_new_chat, handle_tips, handle_feedback

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Create instances for database and API interactions
db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)
hackergpt_api = HackerGPTAPI()

def inform_user_about_premium_status(update, context, user_id):
    if db_manager.check_premium_status(user_id):
        update.message.reply_text("У вас активна премиум подписка.")
    else:
        update.message.reply_text("У вас нет активной премиум подписки.")

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_message = update.message.text      
    logging.info(f"Received message from user {user_id}: {user_message}")

    # Обработка команд
    if user_message.lower() == "начать новый чат":
        handle_new_chat(update, context)
        return
    elif user_message.lower() == "советы по использованию":
        handle_tips(update, context)
        return
    elif user_message.lower() == "предложить улучшение":
        handle_feedback(update, context)
        return

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

# Main function to set up and start the bot
def main() -> None:
    request_kwargs = {
        'read_timeout': 10,
        'connect_timeout': 10
    }
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True, request_kwargs=request_kwargs)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков команд
    dispatcher = updater.dispatcher
    dispatcher.add_handler(command_handlers.start_handler())
    dispatcher.add_handler(command_handlers.status_handler())
    dispatcher.add_handler(command_handlers.payment_handler())
    dispatcher.add_handler(message_handlers.text_handler())
    dispatcher.add_handler(message_handlers.feedback_handler())

    dispatcher.add_handler(CallbackQueryHandler(handle_new_chat, pattern='^new_chat$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_tips, pattern='^tips$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_feedback, pattern='^feedback$'))

    # Настройка планировщика
    scheduler_tasks.setup_scheduler(db_manager)

    # Start the bot
    updater.start_polling()
    updater.idle()

# Program entry point
if __name__ == '__main__':
    main()
