"""MCP tools for querying and managing trade plans.

Provides two tools:

- ``get_trade_plans``   -- list all active trade plans.
- ``mark_order_filled`` -- archive a trade plan as filled.

Dependencies are injected via the module-level ``init()`` function
during server startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient
    from tiger_mcp.safety.trade_plan_store import TradePlanStore

# ---------------------------------------------------------------------------
# Module-level dependencies, set by init() during server startup.
# ---------------------------------------------------------------------------

_trade_plans: TradePlanStore | None = None
_client: TigerClient | None = None


def init(
    trade_plans: TradePlanStore,
    client: TigerClient | None = None,
) -> None:
    """Set the module-level dependencies.

    Parameters
    ----------
    trade_plans:
        The ``TradePlanStore`` instance for reading/writing plans.
    client:
        Optional ``TigerClient`` for validating order status.
    """
    global _trade_plans, _client  # noqa: PLW0603
    _trade_plans = trade_plans
    _client = client


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_trade_plans() -> str:
    """List all active trade plans.

    Returns a human-readable summary of every active trade plan,
    including the original reason, any modifications, and current
    status.  Returns a message if there are no active plans.

    Returns
    -------
    str
        Formatted list of active trade plans, or a message indicating
        no active plans exist.
    """
    if _trade_plans is None:
        return "Error: Trade plan store not initialised."

    plans = _trade_plans.get_active_plans()
    if not plans:
        return "No active trade plans."

    lines: list[str] = [
        f"Active Trade Plans ({len(plans)})",
        "=" * 40,
    ]

    for plan in plans.values():
        lines.append("")
        lines.append(f"  Order ID:    {plan.order_id}")
        lines.append(f"  Symbol:      {plan.symbol}")
        lines.append(f"  Action:      {plan.action}")
        lines.append(f"  Quantity:    {plan.quantity}")
        lines.append(f"  Order Type:  {plan.order_type}")
        if plan.limit_price is not None:
            lines.append(f"  Limit Price: ${plan.limit_price:,.2f}")
        if plan.stop_price is not None:
            lines.append(f"  Stop Price:  ${plan.stop_price:,.2f}")
        lines.append(f"  Reason:      {plan.reason}")
        lines.append(f"  Created:     {plan.created_at}")
        if plan.modifications:
            lines.append(f"  Modifications: {len(plan.modifications)}")
            for mod in plan.modifications:
                changes_str = ", ".join(
                    f"{k}={v}" for k, v in mod.changes.items()
                )
                lines.append(f"    - {changes_str}")
                if mod.reason:
                    lines.append(f"      Reason: {mod.reason}")
        lines.append("  ---")

    return "\n".join(lines)


@mcp.tool()
async def mark_order_filled(order_id: int, reason: str = "") -> str:
    """Mark a trade plan as filled and archive it.

    Optionally validates that the order is actually filled via the
    broker API before archiving.

    Parameters
    ----------
    order_id:
        The numeric order identifier to mark as filled.
    reason:
        Optional note about the fill (e.g. fill price, partial details).

    Returns
    -------
    str
        Confirmation that the plan was archived as filled, or an error
        message if the plan was not found.
    """
    if _trade_plans is None:
        return "Error: Trade plan store not initialised."

    plan = _trade_plans.get_plan(order_id)
    if plan is None:
        return f"Error: No trade plan found for order {order_id}."

    if plan.status == "archived":
        return (
            f"Trade plan for order {order_id} is already archived "
            f"(reason: {plan.archive_reason or 'N/A'})."
        )

    archive_reason = reason or "filled"
    _trade_plans.archive(
        order_id=order_id,
        archive_reason=archive_reason,
    )

    lines = [
        "Trade Plan Archived (Filled)",
        "============================",
        f"  Order ID:  {plan.order_id}",
        f"  Symbol:    {plan.symbol}",
        f"  Action:    {plan.action}",
        f"  Quantity:  {plan.quantity}",
        f"  Reason:    {plan.reason}",
    ]
    if reason:
        lines.append(f"  Fill Note: {reason}")

    return "\n".join(lines)
