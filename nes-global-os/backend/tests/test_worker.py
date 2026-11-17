from datetime import datetime

from sqlalchemy import func, select

from app import models as m
from app.config import settings
from app.db import SessionLocal
from app.routers.system import DAILY_OPS_DEFAULT
from app.worker import due_jobs, tick

TZ = settings.tz


def test_schedule_rules():
    sunday = datetime(2026, 11, 8, 18, 0, tzinfo=TZ)
    assert due_jobs(sunday, DAILY_OPS_DEFAULT) == []
    mon_early = datetime(2026, 11, 9, 8, 0, tzinfo=TZ)
    assert due_jobs(mon_early, DAILY_OPS_DEFAULT) == []
    mon_850 = datetime(2026, 11, 9, 8, 50, tzinfo=TZ)
    assert [j for j, _ in due_jobs(mon_850, DAILY_OPS_DEFAULT)] == ["ceo_briefing"]
    sat_close = datetime(2026, 11, 14, 17, 1, tzinfo=TZ)
    jobs = [j for j, _ in due_jobs(sat_close, DAILY_OPS_DEFAULT)]
    assert "weekly" in jobs and "daily_close" in jobs and "monthly" not in jobs
    # Mon 30 Nov 2026 is the last working day of November
    last = datetime(2026, 11, 30, 17, 5, tzinfo=TZ)
    assert "monthly" in [j for j, _ in due_jobs(last, DAILY_OPS_DEFAULT)]


def test_tick_runs_each_job_once():
    t = datetime(2026, 11, 10, 9, 20, tzinfo=TZ)  # Tuesday 09:20
    first = tick(t)
    assert set(first["jobs"]) == {"ceo_briefing", "task_recommendations"}
    second = tick(t)
    assert second["jobs"] == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).where(m.Report.kind == "ceo_briefing")) >= 1
        hb = db.get(m.Setting, "worker_heartbeat")
        assert hb and hb.value["at"]
