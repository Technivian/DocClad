# My Work vs Command Center — Work Item semantics (PAR-WORK-001)

**Status:** Completed (documentation + boundary note)  
**Date:** 2026-07-21  

## Decision (programme-local clarification; no Charter change)

| Surface | Semantic | Persistence |
|---|---|---|
| **My Work** | Personal actionable queue: projection over authorized assignments / work items the signed-in user can act on | Ephemeral aggregation (`contracts/services/my_work.py` → `assignments`) |
| **Command Center** | Org/portfolio operating view; not a personal task inbox | May materialize `CommandCenterWorkItem` projections |

These must **not** be merged into one module. Pages remain views; authorization remains object-scoped.

## Canonical long-term Work Item

A first-class Work Item aggregate remains Future if/when a PDR requires durable personal work identity beyond assignment projection. Until then, My Work stays a projection.
