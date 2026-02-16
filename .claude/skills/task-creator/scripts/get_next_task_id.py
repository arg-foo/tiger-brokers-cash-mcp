#!/usr/bin/env python3
"""
Get the next available TASK-XXX number by scanning the task directory.

Usage:
    python get_next_task_id.py [--task-dir PATH]
"""
import argparse
import re
from pathlib import Path


def get_next_task_id(task_dir: Path) -> str:
    """
    Scan task directory for TASK-XXX-*.md files and return next available ID.

    Args:
        task_dir: Path to directory containing task files

    Returns:
        Next task ID in format "TASK-XXX"
    """
    if not task_dir.exists():
        return "TASK-001"

    # Pattern to match TASK-XXX-*.md files
    pattern = re.compile(r'TASK-(\d+)-.*\.md')

    max_id = 0
    for file in task_dir.glob("TASK-*.md"):
        match = pattern.match(file.name)
        if match:
            task_num = int(match.group(1))
            max_id = max(max_id, task_num)

    # Next ID
    next_id = max_id + 1
    return f"TASK-{next_id:03d}"


def main():
    parser = argparse.ArgumentParser(
        description="Get next available TASK-XXX number"
    )
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=Path("doc/tasks"),
        help="Path to task directory (default: doc/tasks)"
    )

    args = parser.parse_args()
    next_id = get_next_task_id(args.task_dir)
    print(next_id)


if __name__ == "__main__":
    main()
