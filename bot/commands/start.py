# bot/commands/start.py

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext
from bot.database.manager import DatabaseManager
from config.settings import PREMIUM_SUBSCRIPTION_PRICE, WELCOME_MESSAGE, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR
from bot.commands.payment import get_base_reply_markup

db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

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