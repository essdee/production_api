# Sewing Details — Requirements Document

## 1. Purpose

The **Sewing Details** page provides a single place for production teams to monitor and manage sewing operations of a chosen warehouse. It must surface live production status, allow operator data entry, expose capacity and item-level analytics, and (for planners) maintain final-inspection dates.

## 2. Scope

A Frappe Desk page named *Sewing Details* (route: `sewing-details`) that loads a tabbed Vue dashboard. All operations are scoped to one selected **Warehouse** at a time.

## 3. Users & Roles

| Role | Access |
| --- | --- |
| Operator / Supervisor | All read-only tabs and Data Entry. |
| Production Planner | Everything above + **FI Updates** tab. |
| System Manager | Same as Production Planner. |

## 4. Functional Requirements

### 4.1 Warehouse Selection
- **FR-1.** The user must select a Warehouse before any data is shown.
- **FR-2.** Only Suppliers flagged as company location (`is_company_location = 1`) shall be selectable.
- **FR-3.** Until a Warehouse is selected, the page must show an empty state and disable all tabs.
- **FR-4.** Switching the Warehouse must immediately re-load the current tab against the new selection.

### 4.2 Page-Level Controls
- **FR-5.** A global **Refresh** button must reload the data shown on the active tab without changing the selected Warehouse or tab.
- **FR-6.** Tab navigation must be persistent — leaving and returning to a tab should preserve the user's in-tab state (filters, scroll, edits in progress).

### 4.3 Tab Requirements

#### 4.3.1 Dashboard
- **FR-7.** Display KPI summary of the selected Warehouse's sewing activity (current production status, totals).

#### 4.3.2 Status Summary
- **FR-8.** Show a status-wise breakdown of sewing plans for the Warehouse.

#### 4.3.3 Data Entry
- **FR-9.** Load the editable plan rows for the Warehouse for the relevant period.
- **FR-10.** Allow inline editing of quantity / status fields per row.
- **FR-11.** Provide a Submit action that records the change set as a data-entry log.
- **FR-12.** After a successful submit, the tab must refresh its data automatically.

#### 4.3.4 DPR (Daily Production Report)
- **FR-13.** Show day-wise production figures for the selected Warehouse.

#### 4.3.5 SCR (Sewing Capacity Report)
- **FR-14.** Show capacity vs. planned/actual output for the Warehouse.

#### 4.3.6 Entries
- **FR-15.** List all sewing-plan entries belonging to the selected Warehouse.
- **FR-16.** Allow cancelling an individual entry, with confirmation, when the user has permission.

#### 4.3.7 Monthly Summary
- **FR-17.** Show month-wise aggregated output for the Warehouse.

#### 4.3.8 Item Summary
- **FR-18.** Provide filter options (loaded on tab open) and an item-wise summary view based on the selected filters.

#### 4.3.9 FI Updates *(restricted)*
- **FR-19.** Visible only to **Production Planner** or **System Manager**.
- **FR-20.** Show items / lots awaiting final-inspection date updates for the Warehouse.
- **FR-21.** Allow planners to set / update the FI dates and persist the change.

## 5. Non-Functional Requirements

- **NFR-1. Performance.** Each tab must show data within a reasonable time after Warehouse selection or refresh; loading and error states must be communicated to the user.
- **NFR-2. Touch & Scannability.** The page is used by floor supervisors — controls must be obvious, comfortably tappable, and labelled in plain language.
- **NFR-3. Feedback.** All write actions (Data Entry submit, Entry cancel, FI date update) must show success / failure feedback.
- **NFR-4. Role Enforcement.** Restricted tabs and write endpoints must be gated both in the UI (hidden) and on the server (whitelisted method permissions).
- **NFR-5. Single-page Navigation.** Switching tabs must not cause a full page reload.

## 6. Business Rules

- **BR-1.** A Warehouse is mandatory context for every operation on this page; no cross-warehouse data is shown.
- **BR-2.** A user without the Production Planner / System Manager role may not see or call FI Updates functionality.
- **BR-3.** Cancelling a sewing-plan entry must be reflected in subsequent reads of all tabs.
- **BR-4.** Data Entry submissions must be logged so that changes are auditable.

## 7. Out of Scope

- Creation of new sewing plans (handled in the Sewing Plan DocType form).
- Master-data maintenance for items, suppliers, lots.
- Approvals/workflows beyond entry cancellation and FI-date updates.

## 8. References

- Page: `production_api/production_api/page/sewing_details/`
- Vue root: `production_api/public/js/SewingPlan/SewingPlan.vue`
- Tab components: `production_api/public/js/SewingPlan/components/`
- Backend: `production_api/production_api/doctype/sewing_plan/sewing_plan.py`
