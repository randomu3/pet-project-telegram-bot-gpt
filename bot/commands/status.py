# bot/commands/status.py

from telegram import Update
from telegram.ext import CallbackContext
from bot.database.manager import DatabaseManager
from bot.common import show_user_status
from config.settings import MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR

db_manager = DatabaseManager(MAX_QUESTIONS_PER_HOUR_PREMIUM, MAX_QUESTIONS_PER_HOUR_REGULAR)

def status(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    show_user_status(update, context, user_id)