# bot/handlers/message_handlers.py

from telegram.ext import MessageHandler, Filters
from bot.utils.helpers import process_user_message, process_feedback

def text_handler():
    return MessageHandler(Filters.text & ~Filters.command, process_user_message)

def feedback_handler():
    return MessageHandler(Filters.regex('^Предложить улучшение$'), process_feedback)
