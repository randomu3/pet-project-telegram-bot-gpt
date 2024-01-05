# bot/utils/logging.py

import logging

def setup_logging():
    # Настройте формат, уровень и другие параметры логирования здесь
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

