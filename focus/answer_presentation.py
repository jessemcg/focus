"""GTK-independent presentation helpers for displayed Agent answers.

The displayed answer context line and the saved-answer popover rows must agree
on how a saved timestamp and quality status are worded.  Keeping the formatting
here (no GTK imports) makes the rules directly testable and prevents the two
surfaces from drifting apart.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Stop reasons that mean the answer is an incomplete capture of the model's
# intended final answer, matching ``AgentAnswerSnapshot.partial``.
PARTIAL_STOP_REASONS = frozenset({"length", "error", "aborted"})
PARTIAL_STATUS = "partial"
BEST_EFFORT_CAPTURE = "assistant_fallback"


def format_saved_at(value: str | None) -> str:
    """Format an ISO-8601 timestamp in local time.

    A missing value returns an empty string.  A malformed or unparsable value
    degrades to the original text (stripped) instead of raising, so a damaged
    saved record can still be displayed.
    """
    if value is None:
        return ""
    text = value.strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        # Saved answers store UTC; assume UTC for legacy naive timestamps.
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    return f"{local.strftime('%b')} {local.day}, {local.year}, {local.strftime('%I:%M %p').lstrip('0')}"


def answer_quality_label(
    *,
    status: str | None,
    stop_reason: str | None,
    capture: str | None,
) -> str:
    """Return the explicit quality marker for an answer, or an empty string."""
    if status == PARTIAL_STATUS or (stop_reason or "") in PARTIAL_STOP_REASONS:
        return "Partial"
    if capture == BEST_EFFORT_CAPTURE:
        return "Best-effort"
    return ""


def answer_context_label(
    *,
    is_saved: bool,
    saved_at: str | None = None,
    status: str | None = None,
    stop_reason: str | None = None,
    capture: str | None = None,
) -> str:
    """Compose the one-line context label for the displayed snapshot.

    Historical snapshots read ``Saved answer · <local date>`` and live
    snapshots read ``Latest answer``.  A partial or best-effort answer appends
    an explicit plain-text marker so quality is never conveyed by color alone.
    """
    parts: list[str] = []
    if is_saved:
        stamp = format_saved_at(saved_at)
        parts.append(f"Saved answer · {stamp}" if stamp else "Saved answer")
    else:
        parts.append("Latest answer")
    quality = answer_quality_label(
        status=status,
        stop_reason=stop_reason,
        capture=capture,
    )
    if quality:
        parts.append(quality)
    return " · ".join(parts)
