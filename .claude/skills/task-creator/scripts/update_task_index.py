#!/usr/bin/env python3
"""
Update TASK-INDEX.md with a newly created task.

Usage:
    python update_task_index.py --task-id TASK-029 \
                                --title "API Authentication" \
                                --filename "TASK-029-api-authentication.md" \
                                --complexity "Medium" \
                                --hours "4-6h" \
                                --dependencies "TASK-008, TASK-009" \
                                --phase 3 \
                                --index-path doc/tasks/TASK-INDEX.md
"""
import argparse
import re
from pathlib import Path
from typing import Optional


def parse_hours_range(hours_str: str) -> tuple[int, int]:
    """Parse hour range like '4-6h' into (4, 6)."""
    match = re.match(r'(\d+)-(\d+)h?', hours_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise ValueError(f"Invalid hours format: {hours_str}")


def update_summary_statistics(content: str, complexity: str, hours_str: str) -> str:
    """Update the summary statistics section."""
    min_hours, max_hours = parse_hours_range(hours_str)
    avg_hours = (min_hours + max_hours) / 2

    # Update total tasks
    content = re.sub(
        r'(\*\*Total Tasks\*\*: )(\d+)',
        lambda m: f"{m.group(1)}{int(m.group(2)) + 1}",
        content
    )

    # Update complexity distribution
    complexity_map = {
        'Small': r'(Small \(1-4 hours\): )(\d+)( tasks)',
        'Medium': r'(Medium \(4-8 hours\): )(\d+)( tasks)',
        'Large': r'(Large \(8-10 hours\): )(\d+)( tasks)'
    }

    if complexity in complexity_map:
        pattern = complexity_map[complexity]
        content = re.sub(
            pattern,
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            content
        )

    return content


def add_task_to_phase(
    content: str,
    task_id: str,
    title: str,
    filename: str,
    complexity: str,
    hours: str,
    dependencies: str,
    phase: int
) -> str:
    """Add task row to the appropriate phase table."""

    # Map phase number to section name
    phase_names = {
        1: "Phase 1: Core Infrastructure",
        2: "Phase 2: ETL Pipeline",
        3: "Phase 3: Production Readiness"
    }

    phase_name = phase_names.get(phase)
    if not phase_name:
        raise ValueError(f"Invalid phase: {phase}. Must be 1, 2, or 3")

    # Find the phase section
    phase_pattern = rf'(### {re.escape(phase_name)}.*?\n\n.*?\n.*?\n)(.*?)(\n\n\*\*Phase {phase} Total\*\*:)'

    # Create the new task row
    deps_display = dependencies if dependencies != "None" else "None"
    new_row = f"| {task_id} | [{title}](./{filename}) | {complexity} | {hours} | {deps_display} | PENDING |\n"

    # Insert the new row before the phase total
    def replace_phase(match):
        header = match.group(1)
        table_rows = match.group(2)
        footer = match.group(3)

        # Add new row at the end of the table
        return f"{header}{table_rows}{new_row}{footer}"

    content = re.sub(phase_pattern, replace_phase, content, flags=re.DOTALL)

    return content


def update_phase_total(content: str, phase: int, hours_str: str) -> str:
    """Update the phase total hours."""
    min_hours, max_hours = parse_hours_range(hours_str)
    avg_hours = (min_hours + max_hours) / 2

    # Find current phase total
    pattern = rf'(\*\*Phase {phase} Total\*\*: ~)(\d+)( hours \(~)([\d.]+)( days\))'

    def update_total(match):
        current_hours = int(match.group(2))
        current_days = float(match.group(4))

        new_hours = current_hours + avg_hours
        new_days = new_hours / 8

        return f"{match.group(1)}{int(new_hours)}{match.group(3)}{new_days:.2f}{match.group(5)}"

    content = re.sub(pattern, update_total, content)

    return content


def main():
    parser = argparse.ArgumentParser(
        description="Update TASK-INDEX.md with a new task"
    )
    parser.add_argument("--task-id", required=True, help="Task ID (e.g., TASK-029)")
    parser.add_argument("--title", required=True, help="Task title")
    parser.add_argument("--filename", required=True, help="Task filename")
    parser.add_argument("--complexity", required=True, choices=["Small", "Medium", "Large"])
    parser.add_argument("--hours", required=True, help="Hour estimate (e.g., 4-6h)")
    parser.add_argument("--dependencies", default="None", help="Comma-separated dependencies")
    parser.add_argument("--phase", type=int, required=True, choices=[1, 2, 3])
    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path("doc/tasks/TASK-INDEX.md"),
        help="Path to TASK-INDEX.md"
    )

    args = parser.parse_args()

    # Read current content
    if not args.index_path.exists():
        print(f"❌ Error: {args.index_path} not found")
        return 1

    content = args.index_path.read_text()

    # Update summary statistics
    content = update_summary_statistics(content, args.complexity, args.hours)

    # Add task to phase table
    content = add_task_to_phase(
        content,
        args.task_id,
        args.title,
        args.filename,
        args.complexity,
        args.hours,
        args.dependencies,
        args.phase
    )

    # Update phase total
    content = update_phase_total(content, args.phase, args.hours)

    # Write updated content
    args.index_path.write_text(content)

    print(f"✅ Updated {args.index_path}")
    print(f"   Added {args.task_id} to Phase {args.phase}")

    return 0


if __name__ == "__main__":
    exit(main())
