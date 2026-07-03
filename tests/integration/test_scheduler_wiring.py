from dml_bot.config.schema import AppConfig
from dml_bot.scheduling.jobs import build_scheduler
from tests.integration.telegram_helpers import FakeBot


def test_build_scheduler_registers_all_jobs(lab_setup):
    bot = FakeBot()
    scheduler = build_scheduler(bot, AppConfig())

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {"watch_check", "reminder_check", "cleanup"}
