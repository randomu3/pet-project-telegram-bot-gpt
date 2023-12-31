# bot/hackergpt_api.py

import requests
from os import getenv

class HackerGPTAPI:
    API_URL = 'https://www.hackergpt.co/api/chat/completions'
    API_KEY = getenv('HACKERGPT_API_KEY')

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
        response = requests.post(self.API_URL, json=data, headers=headers)
        response.raise_for_status()
        return response.text