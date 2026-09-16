"""Parsers that turn raw log lines into structured records.

Two formats are supported out of the box:

1. "app" format - a simple application logger line::

       2026-01-15 10:23:45 ERROR db.connector: Connection refused to host 10.0.0.5

   ``TIMESTAMP LEVEL logger_name: message``

2. "access" format - Apache/nginx "combined" access log style::

       127.0.0.1 - - [15/Jan/2026:10:23:45 +0000] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"

Both parsers are pure functions operating on a single line of text and
return ``None`` when the line does not match, so callers can skip
malformed / unparseable lines instead of crashing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, Optional, Union

# ---------------------------------------------------------------------------
# Structured records
# ---------------------------------------------------------------------------


@dataclass
class AppLogRecord:
    """A parsed line from a simple ``TIMESTAMP LEVEL logger: message`` log."""

    timestamp: datetime
    level: str
    logger: str
    message: str
    raw: str

    kind: str = "app"


@dataclass
class AccessLogRecord:
    """A parsed line from an Apache/nginx combined access log."""

    ip: str
    timestamp: datetime
    method: str
    path: str
    protocol: str
    status: int
    size: Optional[int]
    referer: Optional[str]
    agent: Optional[str]
    raw: str

    kind: str = "access"


LogRecord = Union[AppLogRecord, AccessLogRecord]


# ---------------------------------------------------------------------------
# App log format
# ---------------------------------------------------------------------------

_APP_LOG_RE = re.compile(
    r"""^
    (?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s+
    (?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s+
    (?P<logger>[^:]+):\s*
    (?P<message>.*)
    $""",
    re.VERBOSE,
)

_APP_TS_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")

# Normalize a few aliases to a canonical level name.
_LEVEL_ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}


def parse_app_log_line(line: str) -> Optional[AppLogRecord]:
    """Parse one line of the simple app-log format.

    Returns ``None`` if the line does not match the expected shape.
    """
    line = line.rstrip("\n")
    if not line.strip():
        return None

    match = _APP_LOG_RE.match(line)
    if not match:
        return None

    ts_raw = match.group("ts")
    timestamp = None
    for fmt in _APP_TS_FORMATS:
        try:
            timestamp = datetime.strptime(ts_raw, fmt)
            break
        except ValueError:
            continue
    if timestamp is None:
        return None

    level = _LEVEL_ALIASES.get(match.group("level"), match.group("level"))

    return AppLogRecord(
        timestamp=timestamp,
        level=level,
        logger=match.group("logger").strip(),
        message=match.group("message").strip(),
        raw=line,
    )


# ---------------------------------------------------------------------------
# Apache/nginx combined access log format
# ---------------------------------------------------------------------------

_ACCESS_LOG_RE = re.compile(
    r"""^
    (?P<ip>\S+)\s+
    (?P<ident>\S+)\s+
    (?P<user>\S+)\s+
    \[(?P<ts>[^\]]+)\]\s+
    "(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+
    (?P<status>\d{3})\s+
    (?P<size>\S+)
    (?:\s+"(?P<referer>[^"]*)"\s+"(?P<agent>[^"]*)")?
    \s*$""",
    re.VERBOSE,
)

_ACCESS_TS_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


def parse_access_log_line(line: str) -> Optional[AccessLogRecord]:
    """Parse one line of an Apache/nginx combined access log.

    Returns ``None`` if the line does not match the expected shape.
    """
    line = line.rstrip("\n")
    if not line.strip():
        return None

    match = _ACCESS_LOG_RE.match(line)
    if not match:
        return None

    ts_raw = match.group("ts")
    try:
        timestamp = datetime.strptime(ts_raw, _ACCESS_TS_FORMAT)
    except ValueError:
        return None

    size_raw = match.group("size")
    size = None
    if size_raw and size_raw != "-":
        try:
            size = int(size_raw)
        except ValueError:
            size = None

    referer = match.group("referer")
    agent = match.group("agent")

    return AccessLogRecord(
        ip=match.group("ip"),
        timestamp=timestamp,
        method=match.group("method"),
        path=match.group("path"),
        protocol=match.group("protocol"),
        status=int(match.group("status")),
        size=size,
        referer=referer,
        agent=agent,
        raw=line,
    )


# ---------------------------------------------------------------------------
# Combined "try every known format" parsing
# ---------------------------------------------------------------------------

# Order matters: try the more specific/anchored format first.
_PARSERS = (parse_app_log_line, parse_access_log_line)


def parse_line(line: str) -> Optional[LogRecord]:
    """Try each known format against ``line``, returning the first match.

    Returns ``None`` if no parser recognizes the line, so callers can skip
    malformed lines gracefully.
    """
    for parser in _PARSERS:
        record = parser(line)
        if record is not None:
            return record
    return None


def parse_lines(lines: Iterable[str]) -> Iterator[LogRecord]:
    """Parse an iterable of raw lines into structured records.

    Lines that don't match any known format are silently skipped. This
    function is the core decoupling point used by both "parse a whole
    file" and "follow a growing file live" code paths - it only needs
    something iterable of strings.
    """
    for line in lines:
        record = parse_line(line)
        if record is not None:
            yield record
