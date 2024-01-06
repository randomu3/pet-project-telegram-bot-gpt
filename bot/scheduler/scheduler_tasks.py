# bot/scheduler/scheduler_tasks.py

from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime
import logging

def setup_scheduler(db_manager):
    scheduler = BackgroundScheduler(timezone=pytz.utc)  # Явно установить временную зону

    def update_premium_statuses():
        users = db_manager.get_all_users()
        for user in users:
            if user.premium_expiration and user.premium_expiration < datetime.now(pytz.utc):  # Учесть временную зону
                db_manager.update_premium_status(user.id, False, None)

    def check_expired_payment_links():
        db_manager.expire_premium_subscriptions()
        logging.info("Expired premium subscriptions have been updated.")

    scheduler.add_job(update_premium_statuses, 'interval', hours=24)
    scheduler.add_job(check_expired_payment_links, 'interval', hours=24)
    scheduler.start()

