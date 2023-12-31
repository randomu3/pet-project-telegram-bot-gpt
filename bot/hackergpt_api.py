
# bot/hackergpt_api.py

import requests
import logging
from os import getenv

class HackerGPTAPI:
    API_URL = 'https://www.hackergpt.co/api/chat/completions'
    API_KEY = getenv('HACKERGPT_API_KEY')
    TIMEOUT = 10  # Timeout for API requests

    def __init__(self):
        if not self.API_KEY:
            raise ValueError("API key for HackerGPT is not set in environment variables.")

    def send_message(self, message_history):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.API_KEY}'
        }
        data = {
            'model': 'hackergpt',
            'messages': message_history
        }
        try:
            response = requests.post(self.API_URL, json=data, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            # Directly return the response text as the API returns a string
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"API Request error: {e}")
            raise
