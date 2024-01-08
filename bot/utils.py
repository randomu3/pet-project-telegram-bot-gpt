# bot/utils.py
from config import MERCHANT_ID, SECRET_KEY_1, PAYMENT_LINK_LIFETIME_MINUTES, moscow_tz
from bot.database import PaymentLink
from datetime import datetime, timedelta
import hashlib

def generate_payment_link(user_id, amount, db_manager, merchant_id=MERCHANT_ID, secret_key_1=SECRET_KEY_1, currency="RUB", lang="ru"):
    order_id = str(int(datetime.now(moscow_tz).timestamp()))
    expiration_time = datetime.now(moscow_tz) + timedelta(minutes=PAYMENT_LINK_LIFETIME_MINUTES)

    new_link = PaymentLink(user_id=user_id, order_id=order_id, expiration_time=expiration_time)
    db_manager.session.add(new_link)
    db_manager.session.commit()

    sign_str = f"{merchant_id}:{amount}:{secret_key_1}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    payment_url = f"https://pay.kassa.shop/?m={merchant_id}&oa={amount}&o={order_id}&currency={currency}&s={sign}&lang={lang}&us_user_id={user_id}&strd=1"

    return payment_url
