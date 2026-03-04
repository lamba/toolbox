#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone

def parse_epoch(s: str) -> float:
    """
    Accepts integer/float epoch in ms or s.
    Heuristic: >= 1e12 => milliseconds; else seconds.
    """
    val = float(s)
    if val >= 1e12:   # ms
        return val / 1000.0
    return val        # seconds

def main():
    ap = argparse.ArgumentParser(
        description="Convert Unix epoch (ms or s) to human-readable date/time."
    )
    ap.add_argument("epoch", help="Epoch timestamp (ms or s), e.g. 1762380308887")
    ap.add_argument("-f", "--format",
                    default="%Y-%m-%d %H:%M:%S.%f",
                    help="strftime format (default: %(default)s)")
    ap.add_argument("--only", choices=["utc", "local"], default=None,
                    help="Show only UTC or only local (default: both)")
    args = ap.parse_args()

    secs = parse_epoch(args.epoch)
    dt_utc = datetime.fromtimestamp(secs, tz=timezone.utc)
    dt_local = dt_utc.astimezone()  # convert to local tz

    def fmt(dt):
        out = dt.strftime(args.format)
        # trim to milliseconds if format includes %f
        return out[:-3] if "%f" in args.format else out

    if args.only == "utc":
        print(fmt(dt_utc) + "Z")
    elif args.only == "local":
        print(fmt(dt_local), dt_local.tzname() or "")
    else:
        print("UTC  :", fmt(dt_utc) + "Z")
        print("Local:", fmt(dt_local), dt_local.tzname() or "")

if __name__ == "__main__":
    main()