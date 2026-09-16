"""Command line interface for the log aggregator.

Usage examples::

    python aggregate.py samples/app.log --by-level
    python aggregate.py samples/access.log --top-errors 5
    python aggregate.py samples/access.log --requests-per-minute
    python aggregate.py samples/app.log --follow

See README.md for the full flag reference.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Sequence

from .follow import follow_file
from .parser import LogRecord, parse_lines
from .stats import count_by_level, count_by_status, requests_per_minute, top_error_messages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aggregate.py",
        description="Aggregate and summarize application / access log files.",
    )
    parser.add_argument("logfile", help="Path to the log file to process")
    parser.add_argument(
        "--by-level",
        action="store_true",
        help="Show a count of log lines grouped by level (app-format logs)",
    )
    parser.add_argument(
        "--top-errors",
        type=int,
        metavar="N",
        default=None,
        help="Show the N most frequent normalized error messages",
    )
    parser.add_argument(
        "--requests-per-minute",
        "--rpm",
        dest="requests_per_minute",
        action="store_true",
        help="Show request counts bucketed per minute (access-format logs)",
    )
    parser.add_argument(
        "--by-status",
        action="store_true",
        help="Show a count of requests grouped by HTTP status code (access-format logs)",
    )
    parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow the file live like 'tail -f', printing stats as new lines arrive",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between polls when using --follow (default: 0.5)",
    )
    return parser


def _read_lines(path: str) -> Iterable[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line


def print_by_level(records: List[LogRecord]) -> None:
    counts = count_by_level(records)
    print("Log lines by level:")
    if not counts:
        print("  (no app-format log lines found)")
        return
    for level, count in counts.most_common():
        print(f"  {level:<9} {count}")


def print_top_errors(records: List[LogRecord], top_n: int) -> None:
    top = top_error_messages(records, top_n=top_n)
    print(f"Top {top_n} error messages:")
    if not top:
        print("  (no ERROR/CRITICAL app-format log lines found)")
        return
    for message, count in top:
        print(f"  {count:>4}x  {message}")


def print_requests_per_minute(records: List[LogRecord]) -> None:
    buckets = requests_per_minute(records)
    print("Requests per minute:")
    if not buckets:
        print("  (no access-format log lines found)")
        return
    for minute, count in buckets.items():
        print(f"  {minute:%Y-%m-%d %H:%M}  {count}")


def print_by_status(records: List[LogRecord]) -> None:
    counts = count_by_status(records)
    print("Requests by status code:")
    if not counts:
        print("  (no access-format log lines found)")
        return
    for status, count in sorted(counts.items()):
        print(f"  {status}  {count}")


def run_once(records: List[LogRecord], args: argparse.Namespace) -> None:
    ran_something = False

    if args.by_level:
        print_by_level(records)
        ran_something = True

    if args.top_errors is not None:
        if ran_something:
            print()
        print_top_errors(records, args.top_errors)
        ran_something = True

    if args.requests_per_minute:
        if ran_something:
            print()
        print_requests_per_minute(records)
        ran_something = True

    if args.by_status:
        if ran_something:
            print()
        print_by_status(records)
        ran_something = True

    if not ran_something:
        total = len(records)
        print(f"Parsed {total} record(s). No output flag given - see --help.")


def run_follow(args: argparse.Namespace) -> None:
    print(f"Following {args.logfile} (Ctrl+C to stop)...")
    seen: List[LogRecord] = []
    try:
        for line in follow_file(args.logfile, poll_interval=args.poll_interval):
            for record in parse_lines([line]):
                seen.append(record)
                run_once(seen, args)
    except KeyboardInterrupt:
        print("\nStopped following.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.follow:
        run_follow(args)
        return 0

    try:
        lines = list(_read_lines(args.logfile))
    except OSError as exc:
        print(f"error: could not read {args.logfile!r}: {exc}", file=sys.stderr)
        return 1

    records = list(parse_lines(lines))
    run_once(records, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
