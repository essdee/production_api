# Cutting Laysheet Planner — Requirements Document

## 1. Purpose

The **Cutting Laysheet Planner** lets a cutting/IE planner enter an order's size-wise demand together with cutting-room constraints (max plies, max pieces per marker, tolerance, max lays, fabric type) and have the system compute the optimal lay plan. The planner can then compare multiple optimisation strategies and select the one that best fits the floor.

## 2. Scope

A submittable-style Frappe DocType named **Cutting Laysheet Planner** (`CLP-.YYYY.-.#####`) with:
- Input form for order quantities and cutting parameters.
- A server-side optimiser that runs several strategies and returns the best plan plus a comparison of all strategies.
- A custom Vue display (`LayPlanResult`) for reviewing and selecting a strategy.

## 3. Users & Roles

| Role | Access |
| --- | --- |
| Stock User | Create / edit / submit / delete planner records. |
| Transaction User | Create / edit / submit / delete planner records. |
| System Manager | Full access. |

## 4. Functional Requirements

### 4.1 Input Capture

- **FR-1.** The user must be able to set the following input parameters:
  - **Maximum Plies** (Int, required, ≥ 0).
  - **Maximum Pieces Per Marker** (Int, required, ≥ 0).
  - **Tolerance %** (Float, default `3`, ≥ 0).
  - **Maximum Lays** (Int, default `8`, ≥ 0).
  - **Tubular Fabric** (Check, default off). When enabled, all ply counts must be even (folded pairs).
- **FR-2.** The user must be able to enter **Order Details** as a child table of `Size`, `Qty` rows. At least one row is required to optimise.

### 4.2 Optimisation

- **FR-3.** An **Optimize** action must be available in the form header **only when**:
  - the document is saved (not new), AND
  - `order_details` has at least one row, AND
  - `max_plies` and `max_pieces` are both set.
- **FR-4.** Clicking Optimize calls `cutting_laysheet_planner.optimize(doc_name)`, which must:
  - Validate that order rows exist and that `max_plies`/`max_pieces` are set; otherwise show a clear error.
  - Run all available strategies via `lay_optimizer.optimize_all_strategies` using the entered parameters.
  - If no strategy produces a feasible plan, show "No feasible plan found … Try adjusting tolerance or max lays."
  - Persist all feasible strategy results to `lay_details` (one block per strategy) and the full payload to `result_json`.
  - Set the document summary (`total_lays`, `total_order`, `total_cut`, `overcut`, `overcut_pct`, `undercut`, `undercut_pct`) from the **best** strategy returned.
  - Show a confirmation message with the best strategy name and its lay count.
- **FR-5.** While Optimize is running, the form must be frozen with the message "Running all strategies…".

### 4.3 Strategy Comparison & Selection

- **FR-6.** The page must render a Vue-based comparison view (`LayPlanResult`) listing every strategy returned by the optimiser, plus failed strategies (with reason) and de-duplicated strategies (marked as "Same plan as <other>").
- **FR-7.** Available strategies the system may surface include: `milp`, `colgen`, `proportional_decomp`, `ilp`, `order_match`, `balanced`, `single_ratio`.
- **FR-8.** For each strategy the comparison must show: name, description, total lays, unique markers, average pieces/ply, overcut (qty + %), undercut (qty + %), and a **Select** action.
- **FR-9.** Selecting a strategy calls `cutting_laysheet_planner.select_strategy(doc_name, strategy)` which must:
  - Reject the call if no `result_json` is present (i.e. Optimize hasn't run).
  - Resolve "deduplicated" strategies back to their original plan.
  - Update `selected_strategy`, the summary fields, and the per-size deviation HTML to reflect the chosen strategy.
- **FR-10.** Once results exist (`result_json` populated), the legacy fields (`per_size_section`, `lay_details_section`, `result_section`, `selected_strategy`) must be hidden in favour of the Vue view.

### 4.4 Result Presentation

- **FR-11.** Optimisation Summary must display: Total Lays, Total Order Qty, Total Cut Qty, Overcut (qty + %), Undercut (qty + %).
- **FR-12.** Lay Plan must list each lay with: strategy, lay no, plies, ratio (per-size), pieces per ply, total pieces, cut per size.
- **FR-13.** Per-Size Deviation must show, per size: Order, Cut, Diff (coloured red for shortfall, green for overcut), and Deviation %.
- **FR-14.** When no `result_json` is present, the Vue view must show an empty-state prompting the user to click Optimize.

## 5. Non-Functional Requirements

- **NFR-1. Determinism.** Re-running Optimize on the same inputs should produce the same result set (subject to optimiser settings).
- **NFR-2. Feedback.** Optimize must always end with either a success message or a thrown error — no silent failures.
- **NFR-3. Performance.** The form must remain responsive while results render; long computations are bounded by `max_lays` and the strategies enabled in `lay_optimizer`.
- **NFR-4. Data Integrity.** `result_json` is the source of truth for the strategy comparison; summary fields are derived from it on Optimize / Select Strategy.
- **NFR-5. Permission Enforcement.** Optimize and Select Strategy are whitelisted server methods; access is governed by DocType permissions.

## 6. Business Rules

- **BR-1.** Optimisation may not run without at least one order row and both ply / piece limits.
- **BR-2.** With **Tubular Fabric** enabled, every produced lay's `plies` value must be even.
- **BR-3.** A lay plan is feasible only if it respects `max_plies`, `max_pieces`, `max_lays`, and the size totals fall within `tolerance_pct` of the order qty.
- **BR-4.** The "best" strategy used to seed the document summary is the first entry returned by `optimize_all_strategies` (the optimiser's internal ranking).
- **BR-5.** A user-selected strategy must always overwrite the current summary and per-size deviation; the underlying `result_json` is not mutated.
- **BR-6.** Re-running Optimize replaces all previous strategy results (`lay_details` is cleared first).

## 7. Out of Scope

- Generating actual `Cutting Laysheet` documents from a chosen plan (handled separately via the Cutting Laysheet doctype).
- Editing individual lays after optimisation — the planner is regenerative, not hand-editable.
- Marker-image / pattern handling.
- Fabric consumption or costing.

## 8. References

- DocType: `production_api/production_api/doctype/cutting_laysheet_planner/cutting_laysheet_planner.json`
- Controller: `production_api/production_api/doctype/cutting_laysheet_planner/cutting_laysheet_planner.py`
- Client script: `production_api/production_api/doctype/cutting_laysheet_planner/cutting_laysheet_planner.js`
- Optimiser package: `production_api/production_api/utils/lay_optimizer/`
- Vue result view: `production_api/public/js/CuttingLaysheetPlan/LayPlanResult.vue`
- Child tables: `Cutting Laysheet Plan Order`, `Cutting Laysheet Plan Detail`
