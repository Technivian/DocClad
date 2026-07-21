# CLM One Product Map

Canonical boundaries for workspace surfaces. If a screen violates this map, treat it as a product bug.

| Surface | Means | Does not mean |
|--------|--------|----------------|
| **My Work** (`/contracts/my-work/`) | What requires action from the signed-in user | Repository, reporting, org-wide ops |
| **Command Center** (`/`) | Organization-wide operational visibility | Personal inbox |
| **Contracts** (`/contracts/repository/`) | Complete contract repository | Personal action queue |
| **Reviews & Approvals** | Specialist review / approval workspace | Full obligation or privacy workspace |
| **Privacy Reviews** | Specialist privacy workspace | General contract list |
| **Obligations** | Complete obligation workspace | Personal “everything assigned to me” hub |

## Job-to-be-done routes

| Job | Canonical route |
|-----|-----------------|
| What needs my attention now? | My Work |
| How is the portfolio operating? | Command Center |
| Find or manage a contract record | Contracts (repository) |
| Decide on an approval in depth | Reviews & Approvals |
| Complete privacy / DPA work | Privacy Reviews |
| Track renewal and notice obligations | Obligations |

## Implementation notes

- Personal assignments are aggregated in `contracts/services/assignments.py`.
- Specialist inbox personal tabs call `pending_approvals_queryset`, `open_tasks_queryset`, `open_obligations_queryset`, and `reviewer_privacy_packs_queryset`.
- `contracts/services/my_work.py` is a thin facade for backward compatibility.
- Command Center uses org-wide metrics and `CommandCenterWorkItem` projections; it must not use personal assignment querysets.
