"""Alert budget (prompt §10.7, spec Table 7-3 row 7) — pure functions so they can be tested with a frozen clock.

- Critical alerts (official warnings, border at 5 km / 2 km, NO-GO while at sea) always go out.
- At most 3 non-critical alerts a day (IST day).
- Quiet hours (user_prefs, default 21:00-03:30 IST) hold non-critical alerts.
- The same rule for the same boat repeats at most once per 2 hours.
Briefs and the "alerts are on" test push are not alerts: the user asked for them, so the budget does not apply.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Literal

IST = timezone(timedelta(hours=5, minutes=30))
DAILY_NON_CRITICAL = 3
REPEAT_GAP = timedelta(hours=2)
Decision = Literal["send", "hold", "suppress"]


def in_quiet_hours(now: datetime, quiet_from: time, quiet_to: time) -> bool:
    t = now.astimezone(IST).time()
    if quiet_from <= quiet_to:
        return quiet_from <= t < quiet_to
    return t >= quiet_from or t < quiet_to  # wraps midnight (21:00-03:30)


def decide(
    *,
    kind: str,
    critical: bool,
    now: datetime,
    quiet_from: time = time(21, 0),
    quiet_to: time = time(3, 30),
    sent_non_critical_today: int = 0,
    last_same_rule_at: datetime | None = None,
) -> Decision:
    if kind in ("brief", "test", "family"):
        return "send"
    if last_same_rule_at is not None and now - last_same_rule_at < REPEAT_GAP:
        return "suppress"
    if critical:
        return "send"
    if sent_non_critical_today >= DAILY_NON_CRITICAL:
        return "suppress"
    if in_quiet_hours(now, quiet_from, quiet_to):
        return "hold"
    return "send"


def ist_day_start(now: datetime) -> datetime:
    local = now.astimezone(IST)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def brief_due_at(day: datetime, brief_time: time | None, departures: list[time]) -> datetime:
    """When today's brief is due (IST): user_prefs.brief_time if set, else 30 min before the median departure of
    the last 10 trips, else 30 min before 04:00."""
    start = ist_day_start(day)
    if brief_time is not None:
        return start + timedelta(hours=brief_time.hour, minutes=brief_time.minute)
    dep = median_time(departures[:10]) if departures else time(4, 0)
    return start + timedelta(hours=dep.hour, minutes=dep.minute) - timedelta(minutes=30)


def median_time(times: list[time]) -> time:
    mins = sorted(t.hour * 60 + t.minute for t in times)
    n = len(mins)
    m = mins[n // 2] if n % 2 else (mins[n // 2 - 1] + mins[n // 2]) // 2
    return time(m // 60, m % 60)
