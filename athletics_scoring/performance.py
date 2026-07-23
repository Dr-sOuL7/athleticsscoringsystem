"""Performance parsing utilities.

A single, unit-agnostic parser converts a raw ``RESULT`` value into a plain
``float`` that the scoring engine can compare.  The meaning of the number
depends on the event's :class:`~athletics_scoring.events.PerformanceType`:

* ``TIME``   -> the value is a number of **seconds** (lower is better).
* ``DISTANCE`` / ``POINTS`` -> the value is **metres** or **points**
  (higher is better).

Because both the World Athletics table cells *and* the athletes' results are
run through the very same parser, the two are always directly comparable.

Supported textual forms
-----------------------
========================  =====================================
Raw value                 Parsed float (seconds / metres / pts)
========================  =====================================
``"10.87"``               ``10.87``
``"2:05.31"``             ``125.31``   (m:s.cc)
``"1:02:05.3"``           ``3725.3``   (h:m:s)
``"6.72"``                ``6.72``
``7265`` (int)            ``7265.0``   (combined-event points)
========================  =====================================
"""

from __future__ import annotations

# Values that mean "no entry" / "not a real performance".
_EMPTY_TOKENS: frozenset[str] = frozenset({"", "-", "–", "—", "na", "n/a", "none"})


class PerformanceParseError(ValueError):
    """Raised when a raw result string cannot be interpreted."""


def is_empty_token(raw: object) -> bool:
    """Return ``True`` when *raw* represents an absent table entry (``' -'``)."""
    if raw is None:
        return True
    return str(raw).strip().lower() in _EMPTY_TOKENS


def parse_performance(raw: object) -> float:
    """Convert a raw result into a comparable ``float``.

    Times are normalised to **seconds**; distances stay in **metres**;
    combined-event scores stay in **points**.  The colon-separated groups are
    accumulated in base-60 so both ``m:s`` and ``h:m:s`` work transparently.

    Args:
        raw: The cell value (``str``, ``int`` or ``float``).

    Returns:
        The performance as a single floating-point number.

    Raises:
        PerformanceParseError: If *raw* is empty or not a recognised number.
    """
    # Fast path: the workbook stores some cells (combined events) as numbers.
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)

    if raw is None:
        raise PerformanceParseError("empty performance value")

    text = str(raw).strip()
    if text.lower() in _EMPTY_TOKENS:
        raise PerformanceParseError(f"empty performance value: {raw!r}")

    # Some sheets use a leading '+' or stray whitespace inside the string.
    text = text.replace(" ", "")

    try:
        if ":" in text:
            seconds = 0.0
            for group in text.split(":"):
                seconds = seconds * 60.0 + float(group)
            return seconds
        return float(text)
    except ValueError as exc:  # pragma: no cover - message is the useful bit
        raise PerformanceParseError(f"cannot parse performance {raw!r}") from exc
