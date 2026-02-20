"""Shared helpers for order tool modules.

Extracted from ``execution.py`` and ``management.py`` to eliminate
duplication of ``_format_safety_result`` and ``_get_effective_config``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tiger_mcp.config import Settings
    from tiger_mcp.safety.checks import SafetyResult


def format_safety_result(result: SafetyResult) -> str:
    """Format a SafetyResult into human-readable text.

    Errors are listed under a ``SAFETY ERRORS`` heading and warnings
    under ``SAFETY WARNINGS``.  Returns an empty string when there are
    no issues.
    """
    lines: list[str] = []

    if result.errors:
        lines.append("SAFETY ERRORS:")
        for err in result.errors:
            lines.append(f"  - {err}")

    if result.warnings:
        lines.append("SAFETY WARNINGS:")
        for warn in result.warnings:
            lines.append(f"  - {warn}")

    return "\n".join(lines)


def get_effective_config(config: Settings | None) -> Any:
    """Return *config* if set, or a permissive fallback.

    When *config* is ``None`` (e.g. during testing), returns a
    namespace with all safety limits disabled (set to ``0``).
    """
    if config is not None:
        return config

    from types import SimpleNamespace

    return SimpleNamespace(
        max_order_value=0.0,
        daily_loss_limit=0.0,
        max_position_pct=0.0,
    )
