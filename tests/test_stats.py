"""Tests for loganalyzer.stats."""

import unittest
from datetime import datetime, timezone

from loganalyzer.parser import parse_lines
from loganalyzer.stats import (
    count_by_level,
    count_by_status,
    normalize_error_message,
    requests_per_minute,
    top_error_messages,
)

APP_LINES = [
    "2026-01-15 10:23:41 INFO app.startup: Application starting up\n",
    "2026-01-15 10:23:45 DEBUG db.connector: Opening connection pool with size 10\n",
    "2026-01-15 10:24:10 ERROR db.connector: Connection refused to host 10.0.0.5\n",
    "2026-01-15 10:24:15 ERROR db.connector: Connection refused to host 10.0.0.9\n",
    "2026-01-15 10:24:33 ERROR auth.session: User 48213 not found\n",
    "2026-01-15 10:24:40 ERROR auth.session: User 91820 not found\n",
    "2026-01-15 10:24:40 ERROR auth.session: User 91820 not found\n",
    "2026-01-15 10:25:10 CRITICAL app.core: Unhandled exception in worker 7\n",
    "this line is garbage and should be skipped\n",
]

ACCESS_LINES = [
    '203.0.113.7 - - [15/Jan/2026:10:23:01 +0000] "GET /a HTTP/1.1" 200 100\n',
    '203.0.113.7 - - [15/Jan/2026:10:23:45 +0000] "GET /b HTTP/1.1" 200 100\n',
    '203.0.113.9 - - [15/Jan/2026:10:23:59 +0000] "GET /c HTTP/1.1" 404 50\n',
    '203.0.113.7 - - [15/Jan/2026:10:24:02 +0000] "GET /d HTTP/1.1" 200 100\n',
    '203.0.113.7 - - [15/Jan/2026:10:24:33 +0000] "GET /e HTTP/1.1" 500 20\n',
    "not a valid access line at all\n",
]


class TestLevelCounting(unittest.TestCase):
    def test_counts_each_level_correctly(self):
        records = list(parse_lines(APP_LINES))
        counts = count_by_level(records)

        self.assertEqual(counts["INFO"], 1)
        self.assertEqual(counts["DEBUG"], 1)
        self.assertEqual(counts["ERROR"], 5)
        self.assertEqual(counts["CRITICAL"], 1)

    def test_empty_input_gives_empty_counts(self):
        self.assertEqual(count_by_level([]), {})


class TestErrorNormalization(unittest.TestCase):
    def test_strips_ip_addresses(self):
        self.assertEqual(
            normalize_error_message("Connection refused to host 10.0.0.5"),
            "Connection refused to host <IP>",
        )

    def test_strips_plain_numbers(self):
        self.assertEqual(
            normalize_error_message("User 12345 not found"),
            "User <NUM> not found",
        )

    def test_similar_errors_normalize_to_the_same_string(self):
        a = normalize_error_message("Connection refused to host 10.0.0.5")
        b = normalize_error_message("Connection refused to host 10.0.0.9")
        self.assertEqual(a, b)

    def test_top_error_messages_groups_and_ranks_by_frequency(self):
        records = list(parse_lines(APP_LINES))
        top = top_error_messages(records, top_n=5)

        top_dict = dict(top)
        self.assertEqual(top_dict["Connection refused to host <IP>"], 2)
        self.assertEqual(top_dict["User <NUM> not found"], 3)
        # ERROR/CRITICAL only: CRITICAL is included, INFO/DEBUG are not.
        self.assertIn("Unhandled exception in worker <NUM>", top_dict)

    def test_top_error_messages_respects_n(self):
        records = list(parse_lines(APP_LINES))
        top = top_error_messages(records, top_n=1)
        self.assertEqual(len(top), 1)
        # The most frequent normalized message should come first.
        self.assertEqual(top[0][0], "User <NUM> not found")
        self.assertEqual(top[0][1], 3)


class TestRequestsPerMinute(unittest.TestCase):
    def test_buckets_requests_into_correct_minutes(self):
        records = list(parse_lines(ACCESS_LINES))
        buckets = requests_per_minute(records)

        minute_23 = datetime(2026, 1, 15, 10, 23, 0, tzinfo=timezone.utc)
        minute_24 = datetime(2026, 1, 15, 10, 24, 0, tzinfo=timezone.utc)

        self.assertEqual(buckets[minute_23], 3)
        self.assertEqual(buckets[minute_24], 2)
        self.assertEqual(len(buckets), 2)

    def test_buckets_are_sorted_chronologically(self):
        records = list(parse_lines(ACCESS_LINES))
        buckets = requests_per_minute(records)
        self.assertEqual(list(buckets.keys()), sorted(buckets.keys()))

    def test_ignores_non_access_records(self):
        records = list(parse_lines(APP_LINES))
        buckets = requests_per_minute(records)
        self.assertEqual(buckets, {})


class TestStatusCounting(unittest.TestCase):
    def test_counts_by_status_code(self):
        records = list(parse_lines(ACCESS_LINES))
        counts = count_by_status(records)

        self.assertEqual(counts[200], 3)
        self.assertEqual(counts[404], 1)
        self.assertEqual(counts[500], 1)


if __name__ == "__main__":
    unittest.main()
