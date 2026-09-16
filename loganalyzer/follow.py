"""A small "tail -f" style live-follow mode for a growing log file.

The important design choice here is decoupling: this module's only job is
to turn a file on disk into an iterable stream of new lines as they are
appended. It knows nothing about parsing or aggregation. All the actual
aggregation logic in ``stats.py`` operates on plain iterables of lines (or
parsed records), so it can be exercised in unit tests without touching the
filesystem or real time at all - tests just hand it a list/generator of
lines instead of a followed file.
"""

from __future__ import annotations

import time
from typing import IO, Iterator


def follow(file_obj: IO[str], poll_interval: float = 0.5) -> Iterator[str]:
    """Yield new lines appended to ``file_obj`` forever (blocking generator).

    Seeks to the end of the file first, then polls for new content,
    behaving like ``tail -f``. This is intentionally a thin, blocking
    generator over a file handle - it is not unit-tested directly (it
    depends on real time and a real file), but it defers 100% of the
    interesting logic (parsing, counting, bucketing) to functions in
    ``parser.py`` / ``stats.py`` that *are* fully unit-tested.
    """
    file_obj.seek(0, 2)  # seek to end
    while True:
        line = file_obj.readline()
        if not line:
            time.sleep(poll_interval)
            continue
        yield line


def follow_file(path: str, poll_interval: float = 0.5) -> Iterator[str]:
    """Open ``path`` and follow it like ``tail -f``, yielding new lines."""
    with open(path, "r", encoding="utf-8", errors="replace") as file_obj:
        yield from follow(file_obj, poll_interval=poll_interval)
