from datetime import datetime, timedelta, timezone

from hunter.scheduler import CR_TZ, command, initial_plan, next_daily, reschedule


def test_sites_are_staggered():
    now = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)
    plan = initial_plan(now, ["a", "b", "c", "d"], 20, 8)
    assert [plan[f"run:{s}"] - now for s in "abcd"] == [timedelta(minutes=m) for m in (0, 5, 10, 15)]


def test_digest_at_8_costa_rica():
    now = datetime(2026, 9, 23, 15, tzinfo=timezone.utc)  # 09:00 in CR, already past 08:00
    nxt = next_daily(now, 8)
    assert nxt.astimezone(CR_TZ).hour == 8 and nxt.astimezone(CR_TZ).day == 24
    assert reschedule("digest", nxt, 20, 8) == nxt + timedelta(days=1)


def test_commands():
    assert command("run:anuntico")[-3:] == ["run", "--site", "anuntico"]
    assert command("digest")[-1] == "digest"
