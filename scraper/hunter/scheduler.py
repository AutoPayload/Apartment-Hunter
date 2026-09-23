"""Built-in scheduler for Docker: staggered site runs, hourly health check, daily digest.

Each job runs as a subprocess (`python -m hunter ...`) so one crashing site can't take down the loop.
Times use Costa Rica local time (UTC-6, no DST).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from .adapters import ADAPTERS

log = logging.getLogger(__name__)
CR_TZ = timezone(timedelta(hours=-6))


def next_daily(now: datetime, hour: int) -> datetime:
    local = now.astimezone(CR_TZ)
    target = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def initial_plan(now: datetime, sites: list[str], interval_min: int, digest_hour: int) -> dict[str, datetime]:
    """First run time per job. Sites are spread evenly across the interval."""
    step = timedelta(minutes=interval_min) / max(len(sites), 1)
    plan = {f"run:{site}": now + i * step for i, site in enumerate(sites)}
    plan["health"] = now + timedelta(minutes=interval_min * 3)
    plan["digest"] = next_daily(now, digest_hour)
    return plan


def command(job: str) -> list[str]:
    base = [sys.executable, "-m", "hunter"]
    if job.startswith("run:"):
        return base + ["run", "--site", job.split(":", 1)[1]]
    return base + [job]


def reschedule(job: str, when: datetime, interval_min: int, digest_hour: int) -> datetime:
    if job == "digest":
        return next_daily(when + timedelta(minutes=1), digest_hour)
    if job == "health":
        return when + timedelta(hours=1)
    return when + timedelta(minutes=interval_min)


def schedule_loop(interval_min: int = 20, digest_hour: int = 8, sites: list[str] | None = None) -> None:
    sites = sites or list(ADAPTERS)
    plan = initial_plan(datetime.now(timezone.utc), sites, interval_min, digest_hour)
    log.info("scheduler: %d sites every %d min, digest %02d:00 CR", len(sites), interval_min, digest_hour)
    while True:
        job, when = min(plan.items(), key=lambda kv: kv[1])
        wait = (when - datetime.now(timezone.utc)).total_seconds()
        if wait > 0:
            time.sleep(wait)
        log.info("scheduler: %s", job)
        try:
            subprocess.run(command(job), timeout=15 * 60, check=False)
        except subprocess.TimeoutExpired:
            log.error("scheduler: %s timed out", job)
        plan[job] = reschedule(job, when, interval_min, digest_hour)
