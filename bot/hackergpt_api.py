
# bot/hackergpt_api.py

import requests
import logging
from os import getenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class HackerGPTAPI:
    API_URL = 'https://www.hackergpt.co/api/chat/completions'
    API_KEY = getenv('HACKERGPT_API_KEY')
    TIMEOUT = 20  # Timeout for API requests

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
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = session.post(self.API_URL, json=data, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"API Request error: {e}")
            raise
