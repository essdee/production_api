# Vendor Bill Cancellation Approval Design

**Date:** 2026-10-03
**Source application:** `production_api` on Frappe 15 (`mrp3.site`)
**Migration/target application:** `essdee_yrp` on Frappe 16

## Objective

Replace immediate Vendor Bill Tracking cancellation with a two-stage, role-controlled approval flow while preserving data migration compatibility with YRP Bill Tracking.

The implementation must not add fields to MRP Settings or Bill Tracking. It adds two options to the existing `form_status` Select field and hardcodes the workflow roles.

## Roles

- `HR User` requests cancellation and performs the final cancellation after approval.
- `HR Manager` approves a pending cancellation request.
- `System Manager` receives no business-flow bypass.
- Both apps create missing workflow Role records idempotently during install/migrate setup. This is setup data, not an MRP Settings field.

## Statuses and Transitions

Add these options to `form_status` in both source and target metadata:

- `Pending Approval`
- `Cancel Request Approved`

Allowed transitions:

1. A submitted bill in `Open`, `Assigned`, `Reopen`, or `Amended` may move to `Pending Approval` only through an `HR User` request.
2. A bill in `Pending Approval` may move to `Cancel Request Approved` only through an `HR Manager` approval.
3. A bill in `Cancel Request Approved` may be cancelled only by an `HR User`.
4. Successful cancellation continues to use the existing controller lifecycle, which records the cancellation and sets `form_status` to `Cancelled`.

The request and approval APIs reject wrong roles, draft/cancelled documents, statuses outside the transition above, repeated/out-of-order transitions, and bills linked to a purchase invoice. The final cancellation API and `before_cancel` lifecycle guard both enforce the approved state and `HR User` role, preventing bypass through direct RPC or the standard document action.

There is no rejection transition in this scope. A pending request remains pending until approved.

## User Interface

For a submitted bill with neither local nor ERP purchase-invoice links:

- `Open`, `Assigned`, `Reopen`, or `Amended` + `HR User`: show **Request for Cancel**.
- `Pending Approval` + `HR Manager`: show **Approve Cancel Request**.
- `Cancel Request Approved` + `HR User`: show **Cancel**.

The request and approval actions use confirmation prompts. The final Cancel action keeps the existing mandatory cancel-reason dialog.

The existing unconditional Cancel action is removed. The framework's secondary Cancel control remains hidden. Assignment and purchase-invoice creation actions are hidden while cancellation is pending or approved so the document cannot enter a conflicting state.

## Frappe 15 / `production_api`

- Extend `Vendor Bill Tracking.form_status` options in the DocType JSON.
- Add server methods for request and approval transitions.
- Harden the existing cancellation method and the document's `before_cancel` lifecycle hook.
- Update the Vendor Bill Tracking form script to render only state- and role-appropriate actions.
- Add `HR User` and `HR Manager` to idempotent required-role setup.
- Add server and metadata tests for roles, transitions, bypass prevention, invoice-link rejection, and status options.

## Frappe 16 / `essdee_yrp`

The base `yrp` app remains unchanged.

- Add an `essdee_yrp` Property Setter extending `YRP Bill Tracking.form_status` with the two new options.
- Add an Essdee-owned Bill Tracking service with the same role and transition rules.
- Override the base YRP cancellation whitelist route and add a `before_cancel` document hook so direct calls cannot bypass approval.
- Update the existing Essdee YRP Bill Tracking form script to remove the base Cancel action and add the state-driven actions.
- Ensure `HR User` and `HR Manager` exist through Essdee's idempotent setup.
- Add service, UI-contract, metadata, and setup tests.

## Migration Compatibility

`Vendor Bill Tracking.form_status` already maps by the same field name to `YRP Bill Tracking.form_status`; no migration field mapping changes are needed.

The target Property Setter must be included in `essdee_yrp` fixtures and in its explicit Property Setter allowlist. The migration planner already overlays packaged Property Setters on the target schema. Tests will verify that:

- source and target status metadata contain both new values;
- `Pending Approval` is preserved during transformation;
- `Cancel Request Approved` is preserved during transformation;
- the migration plan remains ready with no schema blockers.

## Error Handling and Concurrency

Every server action locks the current database row, reloads it, and validates the persisted state before changing it. Invalid or stale actions fail with a validation or permission error and leave the document unchanged. The final lifecycle guard is authoritative even if the browser UI is bypassed.

## Verification

- Run focused Frappe 15 Vendor Bill Tracking and role-setup tests on `mrp3.site`.
- Run focused Frappe 16 Essdee Bill Tracking, setup, schema, planner, and transformer tests on the configured target test site.
- Run static JavaScript syntax checks for both modified form scripts.
- Run migration-plan validation and confirm zero new schema issues.
- Run the relevant wider application suites where feasible and report any unrelated pre-existing failures separately.

## Scope Exclusions

- No MRP Settings fields or values.
- No new Bill Tracking fields.
- No Frappe Workflow records.
- No rejection action.
- No changes to the base Frappe 16 `yrp` app.
- No commits, per user instruction.
