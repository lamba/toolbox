#!/usr/bin/env python3
"""
AJO Batch Evaluation Time Helper

Usage examples:
  python epoch-ms-duration.py --start 1756942208975 --end 1756943146914
  python epoch-ms-duration.py --start 1693786208 --end 1693789946 --tz America/New_York
  python epoch-ms-duration.py --start 1756942208.975 --end 1756943146.914

The script accepts epoch seconds, milliseconds, or microseconds.
It detects the unit automatically and prints times in UTC and the chosen timezone,
plus the elapsed duration.
"""

from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

def parse_epoch(value: str) -> datetime:
    """Parse an epoch timestamp in seconds, milliseconds, or microseconds to a UTC datetime."""
    try:
        v = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid epoch value: {value}") from e

    # Heuristic for unit detection
    if v >= 1e14:      # microseconds
        seconds = v / 1e6
    elif v >= 1e12:    # milliseconds
        seconds = v / 1e3
    else:              # seconds (can be fractional)
        seconds = v

    return datetime.fromtimestamp(seconds, tz=timezone.utc)

def fmt(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds")

def human_duration(delta: timedelta) -> str:
    total_ms = int(delta.total_seconds() * 1000)
    neg = total_ms < 0
    total_ms = abs(total_ms)
    hours, rem_ms = divmod(total_ms, 3600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    seconds, ms = divmod(rem_ms, 1000)
    sign = "-" if neg else ""
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"

def main():
    ap = argparse.ArgumentParser(description="Convert start/end epochs to ET (or any TZ) and show duration.")
    ap.add_argument("--start", required=True, help="Start time as epoch (sec/ms/us)")
    ap.add_argument("--end", required=True, help="End time as epoch (sec/ms/us)")
    ap.add_argument("--tz", default="America/New_York", help="IANA timezone for local display (default: America/New_York)")
    args = ap.parse_args()

    start_utc = parse_epoch(args.start)
    end_utc = parse_epoch(args.end)

    tz = ZoneInfo(args.tz)

    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)

    duration = end_utc - start_utc

    print("=== AJO Batch Evaluation Timing ===")
    print(f"Timezone: {args.tz}")
    print("-- Start --")
    print(f"UTC: {fmt(start_utc)}")
    print(f"Local: {fmt(start_local)}")
    print("-- End --")
    print(f"UTC: {fmt(end_utc)}")
    print(f"Local: {fmt(end_local)}")
    print("-- Duration --")
    print(f"Elapsed: {human_duration(duration)} (HH:MM:SS.mmm)")

if __name__ == "__main__":
    main()
