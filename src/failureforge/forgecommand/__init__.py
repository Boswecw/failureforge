"""ForgeCommand-shaped read-only morning-report client for FailureForge
(Slice 05). Renders the operator views served by DataForge Local at
``/api/v1/failureforge/operator/...`` to the terminal in a copy-friendly
form. ForgeCommand's UI is the eventual consumer — same JSON shape, same
routes."""

from failureforge.forgecommand.client import (
    OperatorClient,
    render_morning_report_text,
    render_receipt_detail_text,
    render_run_detail_text,
)

__all__ = [
    "OperatorClient",
    "render_morning_report_text",
    "render_run_detail_text",
    "render_receipt_detail_text",
]
