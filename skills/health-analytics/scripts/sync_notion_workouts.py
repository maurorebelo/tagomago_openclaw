#!/usr/bin/env python3
"""
Sync workout rows from Notion into the health database.
- Read NOTION_API_KEY and NOTION_DATABASE_ID from environment
- Fetch workout rows from the Notion database
- Upsert into notion_workouts table by Notion page id
Exit 0 on success. Exit non-zero if credentials missing or API error.
"""

import os

def main():
    if not os.environ.get("NOTION_API_KEY") or not os.environ.get("NOTION_DATABASE_ID"):
        raise SystemExit("NOTION_API_KEY and NOTION_DATABASE_ID required")
    # TODO: implement Notion API fetch and upsert
    raise NotImplementedError("Implement sync_notion_workouts: fetch and upsert by page id")


if __name__ == "__main__":
    main()
