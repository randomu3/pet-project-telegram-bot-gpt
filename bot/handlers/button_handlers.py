# bot/handlers/button_handlers.py

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from datetime import datetime
import logging

# Импорт модулей и функций из вашего проекта (в зависимости от того, где они определены)
from bot.database.manager import DatabaseManager
from bot.api.freekassa import generate_payment_link
from config.settings import MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR, PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1, FEEDBACK_COOLDOWN
from bot.common import check_message_limit

# Создание экземпляров необходимых классов (или их импорт, если они уже созданы в другом месте)
db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

def handle_new_chat(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    user_username = update.callback_query.from_user.username
    logging.info(f"User {user_id} ({user_username}) clicked 'New Chat' button")

    if db_manager.check_premium_status(user_id):
        context.user_data[f'message_count_{user_id}'] = 0
        db_manager.update_message_count(user_id)
        update.callback_query.message.reply_text("Новый чат начат с премиум доступом!")
    else:
        limit_reached = check_message_limit(user_id, context)
        if limit_reached:
            payment_link = generate_payment_link(user_id, PREMIUM_SUBSCRIPTION_PRICE, MERCHANT_ID, SECRET_KEY_1)
            update.callback_query.message.reply_text(
                "Вы достигли лимита сообщений. Приобретите премиум подписку для продолжения.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Купить премиум", url=payment_link)]
                ])
            )
        else:
            context.user_data[f'message_count_{user_id}'] = 0
            update.callback_query.message.reply_text("Новый чат начат!")

def handle_tips(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    user_username = update.callback_query.from_user.username
    logging.info(f"User {user_id} ({user_username}) clicked 'New Chat' button")
    tips_text = '<b>Советы по использованию чата:</b>\n\n' \
                '- Вы можете задавать вопросы напрямую.\n' \
                '- Ответы могут занимать некоторое время, будьте терпеливы.\n' \
                '- Используйте четкие и конкретные вопросы для лучших ответов.\n' \
                '- Попросите Black GPT написать план и действуйте по его пунктам.\n' \
                '- Попросите Black GPT прописывать номера версий при использовании во избежание различий в методах последних версий.\n' \
                '- Для решения сложной проблемы в коде - просите добавить логирование.'
    update.callback_query.message.reply_text(tips_text, parse_mode='HTML')

def handle_feedback(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    user_username = update.callback_query.from_user.username
    logging.info(f"User {user_id} ({user_username}) clicked 'New Chat' button")
    user = db_manager.get_user_by_id(user_id)
    if user and db_manager.check_premium_status(user_id):
        now = datetime.now()
        if user.last_feedback_time is None or (now - user.last_feedbaчck_time).total_seconds() > FEEDBACK_COOLDOWN:
            context.user_data['awaiting_feedback'] = True
            update.callback_query.message.reply_text("Пожалуйста, напишите ваше предложение об улучшении бота.")
            user.last_feedback_time = now
            db_manager.session.commit()
        else:
            cooldown_remaining = int((FEEDBACK_COOLDOWN - (now - user.last_feedback_time).total_seconds()) / 3600)
            update.callback_query.message.reply_text(f"Вы уже отправили предложение об улучшении. Следующее предложение вы сможете отправить через {cooldown_remaining} час(ов).")
    else:
        update.callback_query.message.reply_text("Только премиум-пользователи могут отправлять предложения об улучшении.")
