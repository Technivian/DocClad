"""Backward-compatible facade over the canonical assignments service."""

from contracts.services.assignments import (  # noqa: F401
    DUE_SOON_DAYS,
    PRIORITY_RANK,
    RECENTLY_COMPLETED_DAYS,
    SUMMARY_FILTERS,
    UPCOMING_OBLIGATION_DAYS,
    WORK_TYPE_CHOICES,
    build_filter_options,
    build_summary_counts,
    get_active_work_items,
    get_recently_completed_items,
)
