# Cutting Laysheet Planner

## Purpose

The **Cutting Laysheet Planner** accepts size-wise demand and cutting-room
constraints, runs the Lay Optimizer v4.1 strategy portfolio, and presents the
non-dominated plans for review and selection.

## Inputs

- Maximum Plies: positive integer.
- Maximum Pieces Per Marker: positive integer.
- Tolerance %: 0–100; zero is preserved as exact tolerance.
- Maximum Lays: positive integer.
- Tubular Fabric: every accepted lay must have an even ply count.
- Order Details: unique, non-empty sizes with non-negative integer quantities;
  at least one quantity must be positive.

Saving a changed input invalidates the previous result. Inputs cannot be changed
while an optimization is queued or running.

## Background lifecycle

Optimization never runs inside the initiating HTTP request.

1. **Optimize** saves any dirty form values.
2. The whitelisted controller validates and snapshots the saved inputs.
3. The document is set to **Queued** and a deduplicated job is enqueued on
   Frappe's `long` queue with a 900-second timeout.
4. The worker sets the document to **Running** and invokes the v4.1 portfolio.
5. Every strategy runs in an isolated spawned process and is subject to its own
   timeout.
6. Every returned plan is centrally checked against all hard constraints.
7. Equivalent plans are deduplicated and dominated plans move to the outcome
   list. The remaining Pareto plans are ranked by lays, undercut, overcut, and
   marker count.
8. Results are persisted and the document becomes **Completed**. Unexpected
   failures become **Failed**, store a user-safe message, and create a Frappe
   Error Log.

The form polls a lightweight status method and reloads at completion.

## Production strategies

| Strategy | Priority |
| --- | --- |
| `direct_integer_search` | Deterministic minimum-lay search, then deviation |
| `cp_sat` | Exact CP-SAT minimum lays, then weighted deviation |
| `milp` | Restricted-column MILP |
| `column_generation` | Productive patterns for larger orders |
| `proportional` | Operator-style proportional marker plus cleanup |
| `two_lay_dp` | Strong bounded one/two-lay plans |
| `minimum_deviation` | Exact or closest size fulfillment |
| `balanced` | Fewest lays, then marker density |
| `single_marker` | Reuse one marker across all lays |
| `iterated_greedy` | Fast deterministic feasible alternative |

Historical names such as `colgen`, `ilp`, and `order_match` remain accepted
as API aliases.

## Hard plan constraints

A strategy result is rejected unless:

- the plan contains 1 to Maximum Lays physical lays;
- every ply count is a positive integer not exceeding Maximum Plies;
- tubular ply counts are even;
- every ratio is a non-negative integer;
- every marker contains 1 to Maximum Pieces Per Marker pieces;
- no unknown or zero-demand size is cut; and
- every positive-demand size is within the configured tolerance.

## Stored results

- `optimization_input_json`: immutable input snapshot for the active/latest run.
- `result_json.results`: Pareto-optimal selectable plans.
- `result_json.failed`: infeasible, timed-out, invalid, errored, duplicate, and
  dominated outcomes.
- `lay_details`: lays belonging to the primary Pareto plans.
- Summary fields and `selected_strategy`: derived from the selected result.

The first ranked Pareto plan is selected automatically. Selecting another
successful strategy is persisted through the server method.

## Runtime dependencies

The app declares NumPy 2.x, SciPy 1.14+, and OR-Tools 9.15+ in
`pyproject.toml`. Background workers must be restarted after dependency or
code deployment and must be allowed to spawn child processes.

## Main implementation files

- `production_api/production_api/doctype/cutting_laysheet_planner/`
- `production_api/production_api/utils/lay_optimizer/`
- `production_api/public/js/CuttingLaysheetPlan/LayPlanResult.vue`
- `production_api/production_api/utils/lay_optimizer/test_optimizer_hardening.py`
- `production_api/production_api/utils/lay_optimizer/test_direct_integer_search.py`
