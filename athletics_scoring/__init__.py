"""Inter-College Athletics Meet scoring system.

A production-quality scoring engine built on the official World Athletics
Scoring Tables (2025 edition).  The public sub-modules are:

* :mod:`athletics_scoring.loader`    - read ``.xlsx`` / ``.csv`` input.
* :mod:`athletics_scoring.validator` - validate rows against the tables.
* :mod:`athletics_scoring.tables`    - load & binary-search the scoring tables.
* :mod:`athletics_scoring.scorer`    - the UI-independent scoring engine.
* :mod:`athletics_scoring.writer`    - write the sorted ``.xlsx`` output.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
