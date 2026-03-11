#!/usr/bin/env python3
"""
Answer a natural-language question from the health database.
Usage: python query.py --question "<user question>"
- Map question to safe SQL
- Query DuckDB at data/health/health.duckdb
- Return JSON: stats, date range, optional chart data
Print JSON to stdout. Exit 0 on success.
"""

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True, help="Natural language question")
    args = parser.parse_args()
    # TODO: implement question→SQL, query, return JSON
    raise NotImplementedError("Implement query: NL to SQL, run, return JSON")


if __name__ == "__main__":
    main()
