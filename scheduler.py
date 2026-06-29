from apscheduler.schedulers.background import BackgroundScheduler
from database import reset_slots

# Runs in a background thread — does not block the FastAPI event loop
scheduler = BackgroundScheduler()


def start_scheduler():
    """Schedule the daily midnight slot reset and start the scheduler."""
    # cron trigger: fires every day at 00:00
    scheduler.add_job(reset_slots, "cron", hour=0, minute=0, id="daily_reset")
    scheduler.start()


def stop_scheduler():
    """Cleanly shut down the scheduler on app exit."""
    scheduler.shutdown()
