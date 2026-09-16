"""Tests for loganalyzer.parser."""

import unittest
from datetime import datetime

from loganalyzer.parser import (
    AccessLogRecord,
    AppLogRecord,
    parse_access_log_line,
    parse_app_log_line,
    parse_line,
    parse_lines,
)


class TestAppLogParsing(unittest.TestCase):
    def test_parses_valid_app_log_line(self):
        line = "2026-01-15 10:24:10 ERROR db.connector: Connection refused to host 10.0.0.5"
        record = parse_app_log_line(line)

        self.assertIsInstance(record, AppLogRecord)
        self.assertEqual(record.timestamp, datetime(2026, 1, 15, 10, 24, 10))
        self.assertEqual(record.level, "ERROR")
        self.assertEqual(record.logger, "db.connector")
        self.assertEqual(record.message, "Connection refused to host 10.0.0.5")

    def test_normalizes_warn_and_fatal_aliases(self):
        warn = parse_app_log_line("2026-01-15 10:24:10 WARN x: something")
        fatal = parse_app_log_line("2026-01-15 10:24:10 FATAL x: something")

        self.assertEqual(warn.level, "WARNING")
        self.assertEqual(fatal.level, "CRITICAL")

    def test_app_log_line_via_generic_dispatcher(self):
        line = "2026-01-15 10:23:41 INFO app.startup: Application starting up"
        record = parse_line(line)

        self.assertIsInstance(record, AppLogRecord)
        self.assertEqual(record.level, "INFO")


class TestAccessLogParsing(unittest.TestCase):
    def test_parses_valid_combined_access_log_line(self):
        line = (
            '203.0.113.7 - - [15/Jan/2026:10:23:01 +0000] '
            '"GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"'
        )
        record = parse_access_log_line(line)

        self.assertIsInstance(record, AccessLogRecord)
        self.assertEqual(record.ip, "203.0.113.7")
        self.assertEqual(record.method, "GET")
        self.assertEqual(record.path, "/index.html")
        self.assertEqual(record.protocol, "HTTP/1.1")
        self.assertEqual(record.status, 200)
        self.assertEqual(record.size, 2326)
        self.assertEqual(record.timestamp.year, 2026)
        self.assertEqual(record.timestamp.hour, 10)
        self.assertEqual(record.timestamp.minute, 23)

    def test_access_log_line_via_generic_dispatcher(self):
        line = (
            '198.51.100.23 - - [15/Jan/2026:10:23:44 +0000] '
            '"POST /api/login HTTP/1.1" 401 89 "-" "curl/8.4.0"'
        )
        record = parse_line(line)

        self.assertIsInstance(record, AccessLogRecord)
        self.assertEqual(record.status, 401)

    def test_access_log_without_referer_and_agent(self):
        line = '10.0.0.1 - - [15/Jan/2026:10:23:44 +0000] "GET / HTTP/1.1" 200 100'
        record = parse_access_log_line(line)

        self.assertIsInstance(record, AccessLogRecord)
        self.assertIsNone(record.referer)
        self.assertIsNone(record.agent)


class TestMalformedLines(unittest.TestCase):
    def test_malformed_line_returns_none_instead_of_raising(self):
        self.assertIsNone(parse_line("this is not a log line at all"))
        self.assertIsNone(parse_app_log_line("not-a-timestamp INFO foo: bar"))
        self.assertIsNone(parse_access_log_line("also not a valid access log line"))

    def test_blank_line_returns_none(self):
        self.assertIsNone(parse_line(""))
        self.assertIsNone(parse_line("\n"))
        self.assertIsNone(parse_line("   \n"))

    def test_parse_lines_skips_malformed_entries_without_crashing(self):
        lines = [
            "2026-01-15 10:23:41 INFO app.startup: Application starting up\n",
            "totally bogus line\n",
            '203.0.113.7 - - [15/Jan/2026:10:23:01 +0000] "GET / HTTP/1.1" 200 100\n',
            "",
            "another bogus line that matches nothing\n",
        ]

        records = list(parse_lines(lines))

        self.assertEqual(len(records), 2)
        self.assertIsInstance(records[0], AppLogRecord)
        self.assertIsInstance(records[1], AccessLogRecord)


if __name__ == "__main__":
    unittest.main()
