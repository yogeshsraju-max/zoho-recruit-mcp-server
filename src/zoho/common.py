"""Shared helpers for the Zoho domain modules.

Zoho Recruit's search endpoint accepts a ``criteria`` string of the form::

    (Field:operator:value)
    ((Field1:equals:A)and(Field2:starts_with:B))

Supported operators include: equals, not_equal, starts_with, in, between,
greater_than, greater_equal, less_than, less_equal. Free-text "contains"-style
matching is done via the separate ``word`` parameter, not criteria.
"""

from __future__ import annotations

from typing import Any, Iterable

# ---------------------------------------------------------------------------
# NOTE: Module API names. These are the default Zoho Recruit module names.
# If your org renamed modules, override here or via configuration.
# ---------------------------------------------------------------------------
MODULE_CANDIDATES = "Candidates"
MODULE_JOBS = "Job_Openings"
MODULE_INTERVIEWS = "Interviews"

_ALLOWED_OPS = {
    "equals",
    "not_equal",
    "starts_with",
    "in",
    "between",
    "greater_than",
    "greater_equal",
    "less_than",
    "less_equal",
}


def _escape(value: str) -> str:
    # Zoho uses parentheses and colons as control chars in criteria.
    return str(value).replace("(", "\\(").replace(")", "\\)").replace(":", "\\:")


def criterion(field: str, op: str, value: Any) -> str:
    if op not in _ALLOWED_OPS:
        raise ValueError(f"Unsupported criteria operator: {op}")
    if op == "in":
        if not isinstance(value, (list, tuple, set)):
            value = [value]
        joined = ",".join(_escape(str(v)) for v in value)
        return f"({field}:in:{joined})"
    return f"({field}:{op}:{_escape(str(value))})"


def and_(*clauses: str) -> str:
    parts = [c for c in clauses if c]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + "and".join(parts) + ")"


def or_(*clauses: str) -> str:
    parts = [c for c in clauses if c]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + "or".join(parts) + ")"


def records_from(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the ``data`` array out of a Zoho list/search response."""
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if isinstance(data, list):
        return data
    return []


def first_record(response: dict[str, Any]) -> dict[str, Any] | None:
    recs = records_from(response)
    return recs[0] if recs else None


def page_info(response: dict[str, Any]) -> dict[str, Any]:
    info = response.get("info") if isinstance(response, dict) else None
    return info if isinstance(info, dict) else {}


def join_skills(skills: Iterable[str] | str | None) -> str | None:
    if skills is None:
        return None
    if isinstance(skills, str):
        return skills
    return ", ".join(s for s in skills if s)
