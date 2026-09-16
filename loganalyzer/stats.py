"""Aggregation logic: level counts, error grouping, and time bucketing.

Everything here operates on already-parsed records (see ``parser.py``),
so it is trivially unit-testable and decoupled from any notion of files
or "live" streams.
"""

from __future__ import annotations

import re
from collections import Counter, OrderedDict
from datetime import datetime
from typing import Iterable, List, Tuple

from .parser import AccessLogRecord, AppLogRecord, LogRecord

# ---------------------------------------------------------------------------
# Level counting
# ---------------------------------------------------------------------------


def count_by_level(records: Iterable[LogRecord]) -> Counter:
    """Count how many records fall into each log level.

    Only ``AppLogRecord`` instances carry a level; other record kinds are
    ignored.
    """
    counter: Counter = Counter()
    for record in records:
        if isinstance(record, AppLogRecord):
            counter[record.level] += 1
    return counter


# ---------------------------------------------------------------------------
# Error message normalization / grouping
# ---------------------------------------------------------------------------

_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_HEX_ID_RE = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_NUM_RE = re.compile(r"\d+")
_WS_RE = re.compile(r"\s+")


def normalize_error_message(message: str) -> str:
    """Normalize an error message so similar errors group together.

    Strips out variable pieces that would otherwise make two
    functionally-identical errors look distinct: IP addresses, long
    hex/id-looking tokens, and any run of digits (request ids, ports,
    user ids, etc). Whitespace is collapsed too.

    >>> normalize_error_message("Connection refused to host 10.0.0.5")
    'Connection refused to host <IP>'
    >>> normalize_error_message("User 12345 not found")
    'User <NUM> not found'
    """
    text = _IP_RE.sub("<IP>", message)
    text = _HEX_ID_RE.sub("<ID>", text)
    text = _NUM_RE.sub("<NUM>", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


_ERROR_LEVELS = {"ERROR", "CRITICAL"}


def top_error_messages(
    records: Iterable[LogRecord], top_n: int = 5
) -> List[Tuple[str, int]]:
    """Return the ``top_n`` most frequent normalized error messages.

    Only ``AppLogRecord`` instances at ERROR/CRITICAL level are considered.
    Returns a list of ``(normalized_message, count)`` tuples, most frequent
    first (ties broken by first-seen order, matching ``Counter.most_common``).
    """
    counter: Counter = Counter()
    for record in records:
        if isinstance(record, AppLogRecord) and record.level in _ERROR_LEVELS:
            counter[normalize_error_message(record.message)] += 1
    return counter.most_common(top_n)


# ---------------------------------------------------------------------------
# Requests-per-minute time bucketing (access logs)
# ---------------------------------------------------------------------------


def requests_per_minute(records: Iterable[LogRecord]) -> "OrderedDict[datetime, int]":
    """Bucket access-log requests into per-minute counts.

    Only ``AccessLogRecord`` instances are considered. Returns an
    ``OrderedDict`` mapping a minute-truncated ``datetime`` (seconds and
    microseconds zeroed out) to the number of requests seen in that
    minute, sorted chronologically.
    """
    buckets: Counter = Counter()
    for record in records:
        if isinstance(record, AccessLogRecord):
            bucket = record.timestamp.replace(second=0, microsecond=0)
            buckets[bucket] += 1

    ordered: "OrderedDict[datetime, int]" = OrderedDict()
    for bucket in sorted(buckets):
        ordered[bucket] = buckets[bucket]
    return ordered


# ---------------------------------------------------------------------------
# Status code counting (small extra, handy for access logs)
# ---------------------------------------------------------------------------


def count_by_status(records: Iterable[LogRecord]) -> Counter:
    """Count access-log records by HTTP status code."""
    counter: Counter = Counter()
    for record in records:
        if isinstance(record, AccessLogRecord):
            counter[record.status] += 1
    return counter
