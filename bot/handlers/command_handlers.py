# bot/handlers/command_handlers.py

from telegram.ext import CommandHandler
from bot.commands import start, status, payment

def start_handler():
    return CommandHandler("start", start.start)

def status_handler():
    return CommandHandler("status", status.status)

def payment_handler():
    return CommandHandler("payment", payment.handle_payment)