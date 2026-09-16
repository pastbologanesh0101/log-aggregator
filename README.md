# Log Aggregator

A small, pure-stdlib Python CLI that parses log files and turns them into
useful aggregate stats: counts by level, top recurring (normalized) error
messages, and requests-per-minute time buckets for access logs. No external
services or dependencies required.

## Supported log formats

The parser tries each known format against every line and skips anything
that doesn't match (malformed/unparseable lines are dropped, not crashed
on).

**1. "app" format** - a simple application logger line:

```
TIMESTAMP LEVEL logger_name: message
```

```
2026-01-15 10:24:10 ERROR db.connector: Connection refused to host 10.0.0.5
```

- Timestamp: `YYYY-MM-DD HH:MM:SS` (a `T` separator is also accepted)
- Level: `DEBUG`, `INFO`, `WARNING` (or `WARN`), `ERROR`, `CRITICAL` (or `FATAL`)
- Logger name: anything up to the first `:`
- Message: the rest of the line

**2. Apache/nginx "combined" access log format:**

```
203.0.113.7 - - [15/Jan/2026:10:23:01 +0000] "GET /index.html HTTP/1.1" 200 2326 "-" "Mozilla/5.0"
```

`ip ident user [timestamp] "METHOD path protocol" status size "referer" "user-agent"`.
The referer/user-agent pair is optional.

## Installation

No dependencies beyond the Python standard library. Requires Python 3.11+.

```bash
git clone <this-repo>
cd log-aggregator
```

## CLI usage

```
python aggregate.py <logfile> [flags]
```

| Flag | Description |
|---|---|
| `--by-level` | Count log lines grouped by level (app-format logs) |
| `--top-errors N` | Show the N most frequent normalized error messages |
| `--requests-per-minute`, `--rpm` | Requests bucketed per minute (access-format logs) |
| `--by-status` | Count requests grouped by HTTP status code (access-format logs) |
| `--follow`, `-f` | Follow the file live, like `tail -f`, printing updated stats as new lines arrive |
| `--poll-interval SECONDS` | Poll interval used with `--follow` (default `0.5`) |

Flags can be combined; each requested section is printed in turn.

### Examples

```bash
python aggregate.py samples/app.log --by-level
```

```
Log lines by level:
  ERROR     7
  INFO      6
  DEBUG     2
  WARNING   2
  CRITICAL  2
```

```bash
python aggregate.py samples/app.log --top-errors 5
```

```
Top 5 error messages:
     3x  Connection refused to host <IP>
     2x  User <NUM> not found
     2x  Unhandled exception in worker <NUM>: division by zero
     2x  Payment <ID> failed for order <NUM>
```

Error messages are normalized before counting so near-identical errors
(differing only by IP address, numeric id, or long hex id) are grouped
together - e.g. `Connection refused to host 10.0.0.5` and
`Connection refused to host 10.0.0.9` both collapse to
`Connection refused to host <IP>`.

```bash
python aggregate.py samples/access.log --requests-per-minute
```

```
Requests per minute:
  2026-01-15 10:23  5
  2026-01-15 10:24  4
  2026-01-15 10:25  3
```

```bash
python aggregate.py samples/access.log --by-status
```

```
Requests by status code:
  200  7
  204  1
  401  1
  404  1
  500  2
```

Live-follow a growing log file (like `tail -f`), re-printing the requested
stats as each new line arrives:

```bash
python aggregate.py /var/log/app.log --by-level --follow
```

## Project layout

```
aggregate.py            # thin CLI entry point
loganalyzer/
  parser.py             # line -> structured record (per format), skips malformed lines
  stats.py              # aggregation: level counts, error normalization/grouping, time bucketing
  follow.py             # tail -f style live file following (decoupled from aggregation logic)
  cli.py                # argparse wiring + output formatting
samples/
  app.log                # sample app-format log
  access.log              # sample access-format log
tests/
  test_parser.py
  test_stats.py
```

The aggregation logic in `stats.py` operates purely on iterables of parsed
records (or, via `parser.parse_lines`, on any iterable of raw lines) - it
has no knowledge of files, sockets, or real time. That's what makes
`--follow` mode testable: `follow.py` is the only piece that touches a real
file and polls with `time.sleep`, and all the actual counting/grouping/
bucketing it feeds into is unit tested directly on plain lists of strings.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

or, if you have pytest installed:

```bash
pytest tests/
```

Tests cover: parsing each log format correctly, level counting, error
message normalization/grouping, requests-per-minute time bucketing, and
graceful handling of malformed/unparseable lines (skipped, not crashed on).

Continuous integration (`.github/workflows/tests.yml`) runs the test suite
on Python 3.11 and 3.12 on every push and pull request.

## License

MIT - see [LICENSE](LICENSE).
