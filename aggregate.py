#!/usr/bin/env python3
"""Thin entry point: ``python aggregate.py <logfile> [flags]``.

All the actual logic lives in the ``loganalyzer`` package so it can be
imported and unit tested directly.
"""

import sys

from loganalyzer.cli import main

if __name__ == "__main__":
    sys.exit(main())
