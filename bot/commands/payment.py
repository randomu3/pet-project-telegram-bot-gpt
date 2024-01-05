# bot/commands/payment.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext
from bot.api.freekassa import generate_payment_link
from config.settings import PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1, MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR
from bot.database.manager import DatabaseManager
from bot.common import check_message_limit
import logging

db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

def handle_payment(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE)
    update.message.reply_text(
        "Для приобретения премиум подписки перейдите по ссылке:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Оплатить", url=payment_link)]
        ])
    )

def handle_new_chat_button(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    # Логирование нажатия кнопки нового чата
    logging.info(f"User {user_id} clicked 'New Chat' button")

    if db_manager.check_premium_status(user_id):
        context.user_data[f'message_count_{user_id}'] = 0
        db_manager.update_message_count(user_id)  # Обнуляем счетчик сообщений в базе данных
        update.message.reply_text("Новый чат начат с премиум доступом!")
    else:
        # Проверка лимита сообщений
        limit_reached = check_message_limit(user_id, context)
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

# Вспомогательные функции
def get_base_reply_markup():
    new_chat_button = KeyboardButton('Начать новый чат')
    tips_button = KeyboardButton('Советы по использованию')
    feedback_button = KeyboardButton('Предложить улучшение')
    return ReplyKeyboardMarkup([[new_chat_button], [tips_button], [feedback_button]], resize_keyboard=True, one_time_keyboard=False)