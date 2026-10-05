# Vendor Bill Cancellation Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require an HR User cancellation request and HR Manager approval before an HR User can cancel Vendor Bill Tracking in Frappe 15 and migrated YRP Bill Tracking in Frappe 16.

**Architecture:** Each app owns a small server-authoritative state machine using the existing `form_status` field. `production_api` changes its native DocType controller; `essdee_yrp` extends base YRP with a controller subclass, Property Setter, form script, and setup records while leaving the `yrp` app unchanged. Migration retains the existing identity mapping for `form_status` and gains schema/value regression coverage.

**Tech Stack:** Frappe 15/16, Python, JavaScript, DocType JSON, Frappe fixtures, `FrappeTestCase`/`unittest`.

**Spec:** `docs/superpowers/specs/2026-10-03-vendor-bill-cancel-approval-design.md`

## Global Constraints

- Do not add or change MRP Settings fields.
- Do not add Bill Tracking fields; only extend existing `form_status` options.
- Hardcode role names exactly as `HR User` and `HR Manager`.
- Do not grant `System Manager` a business-flow bypass.
- Keep the base Frappe 16 `yrp` app unchanged.
- Preserve all unrelated dirty-worktree changes in `essdee_yrp`, especially `hooks.py`.
- Do not create commits.

## Review Focus

- A direct RPC or standard document cancellation before approval must fail and leave the submitted document unchanged (Tasks 2 and 4).
- Stale or repeated request/approval actions must fail instead of silently skipping state validation (Tasks 2 and 4).
- Either purchase-invoice link must block starting or advancing the cancellation flow (Tasks 2 and 4).
- Users holding both HR roles must still follow the two distinct state transitions; one call cannot request and approve (Tasks 2 and 4).
- Migrated rows carrying either new status must remain valid and unchanged on the target schema (Task 6).

---

### Task 1: Frappe 15 Status Metadata and Required Roles

**Files:**
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.json`
- Modify: `production_api/production_api/doctype/mrp_settings/test_mrp_settings.py` only if no focused metadata test file is preferable
- Modify: `production_api/setup/role_setup.py`
- Modify: `production_api/setup/test_role_setup.py`
- Test: `production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py`

**Interfaces:**
- Produces: `form_status` options containing `Pending Approval` and `Cancel Request Approved`; setup-created `HR User` and `HR Manager` Role records.

- [ ] **Step 1: Write failing metadata and setup tests**

Add tests asserting both exact status strings occur once in `Vendor Bill Tracking.form_status`, and `REQUIRED_ROLES` contains both hardcoded roles with Desk access.

- [ ] **Step 2: Run the focused tests and verify RED**

Run from `frappe-15/sites`:
`../env/bin/python -m frappe.utils.bench_helper frappe --site mrp3.site run-tests --app production_api --module production_api.production_api.doctype.vendor_bill_tracking.test_vendor_bill_tracking --module production_api.setup.test_role_setup`

Expected: failures for missing status options and `HR Manager` setup.

- [ ] **Step 3: Extend metadata and role setup minimally**

Append the two status options without reordering existing values. Add `HR User` and `HR Manager` to `REQUIRED_ROLES` with `desk_access: 1`.

- [ ] **Step 4: Re-run focused tests and verify GREEN**

Expected: metadata/setup assertions pass.

### Task 2: Frappe 15 Server-Authoritative State Machine

**Files:**
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.py`
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py`

**Interfaces:**
- Produces: `request_vendor_bill_cancellation(name: str) -> None`, `approve_vendor_bill_cancellation(name: str) -> None`, hardened `cancel_vendor_bill(name: str, cancel_reason: str) -> None`.
- Produces constants: `CANCEL_REQUEST_ROLE`, `CANCEL_APPROVER_ROLE`, `CANCEL_PENDING_STATUS`, `CANCEL_APPROVED_STATUS`, `CANCEL_REQUESTABLE_STATUSES`.
- Consumes: existing `VendorBillTracking.before_cancel` and purchase-invoice link fields.

- [ ] **Step 1: Write failing request-transition tests**

Cover HR User success from each requestable status, wrong-role denial, draft/cancelled denial, linked `purchase_invoice`/`mrp_purchase_invoice` denial, and repeated request denial. Assert failures do not change persisted status.

- [ ] **Step 2: Run request tests and verify RED**

Expected: import or missing-method failures.

- [ ] **Step 3: Implement locked request transition**

Add shared helpers that require one exact role, lock the row with `for_update=True`, reload it, validate `docstatus == 1`, validate both invoice links are empty, and validate the current status. Save `Pending Approval` with permission bypass only after these checks.

- [ ] **Step 4: Run request tests and verify GREEN**

- [ ] **Step 5: Write failing approval-transition tests**

Cover HR Manager success only from `Pending Approval`, wrong-role denial, out-of-order/repeated approval denial, both-role user still requiring two calls, and invoice-link denial.

- [ ] **Step 6: Run approval tests and verify RED**

- [ ] **Step 7: Implement `approve_vendor_bill_cancellation`**

Reuse the locked-document and invoice-link helpers; save `Cancel Request Approved` only after all checks.

- [ ] **Step 8: Run approval tests and verify GREEN**

- [ ] **Step 9: Write failing final-cancellation bypass tests**

Assert the whitelist method and direct `doc.cancel()` both reject non-approved status and non-HR User sessions, while approved HR User cancellation stores the reason, reaches `docstatus == 2`, and ends at `Cancelled` with the existing history entry.

- [ ] **Step 10: Run cancellation tests and verify RED**

- [ ] **Step 11: Harden final cancellation**

Validate approved persisted status and `HR User` in `VendorBillTracking.before_cancel` before `set_cancelled_log`; keep `cancel_vendor_bill` as the reason-setting entry point.

- [ ] **Step 12: Run the complete Vendor Bill Tracking test module and verify GREEN**

### Task 3: Frappe 15 Form Actions

**Files:**
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.js`
- Test: `production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py`

**Interfaces:**
- Consumes: Task 2 whitelist methods and exact status/role strings.
- Produces: state-specific **Request for Cancel**, **Approve Cancel Request**, and **Cancel** actions.

- [ ] **Step 1: Add a failing source-contract test for form actions**

Assert the script calls both new endpoints, gates actions by the exact roles/statuses, removes the old unconditional Cancel path, retains the mandatory cancel-reason dialog, and suppresses Assign/PI creation during pending or approved cancellation.

- [ ] **Step 2: Run the source-contract test and verify RED**

- [ ] **Step 3: Refactor the refresh handler**

Add small predicates for invoice links and cancellation state. Use confirmation prompts for request/approval, retain the existing final cancel dialog, hide the framework secondary action, and render no conflicting actions in either cancellation state.

- [ ] **Step 4: Run the test and JavaScript syntax check**

Run: `node --check production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.js`

Expected: test PASS and syntax exit code 0.

### Task 4: Frappe 16 Essdee Metadata, Roles, and Server State Machine

**Files:**
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/overrides/bill_tracking.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/test_bill_tracking_cancellation.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/hooks.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/setup.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/test_setup.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/fixtures/property_setter.json`

**Interfaces:**
- Produces: `EssdeeYRPBillTracking(YRPBillTracking)` with guarded `before_cancel`.
- Produces: `request_bill_cancellation(name: str) -> None` and `approve_bill_cancellation(name: str) -> None` in the same focused module.
- Produces: Property Setter `YRP Bill Tracking-form_status-options`.
- Consumes: base YRP controller behavior through `super().before_cancel()`.

- [ ] **Step 1: Write failing fixture/setup tests**

Assert the Property Setter contains all existing statuses plus both new statuses, its name appears in the hooks allowlist, `HR User`/`HR Manager` are in `MRP_SCHEMA_ROLES`, and setup remains idempotent.

- [ ] **Step 2: Run focused tests on `erp-migration-test.site` and verify RED**

Run from `frappe-16/sites`:
`../env/bin/python -m frappe.utils.bench_helper frappe --site erp-migration-test.site run-tests --app essdee_yrp --module essdee_yrp.test_setup --module essdee_yrp.test_bill_tracking_cancellation`

- [ ] **Step 3: Add the Property Setter and role setup**

Append one fixture row and one hooks allowlist entry without disturbing existing fixture rows or unrelated dirty `hooks.py` changes. Add both HR roles to idempotent setup.

- [ ] **Step 4: Run fixture/setup tests and verify GREEN**

- [ ] **Step 5: Write failing Essdee transition and bypass tests**

Mirror Task 2 coverage using `YRP Bill Tracking`, `purchase_invoice`, and `erp_purchase_invoice`. Additionally assert the subclass calls base cancellation logging only after authorization succeeds.

- [ ] **Step 6: Run state-machine tests and verify RED**

- [ ] **Step 7: Implement the Essdee controller extension and methods**

Register the subclass in `override_doctype_class`. Use the same constants, row locking, exact roles, statuses, and transition rules as Frappe 15; call `super().before_cancel()` only after final authorization.

- [ ] **Step 8: Run the complete Essdee cancellation test module and verify GREEN**

### Task 5: Frappe 16 Essdee Form Actions

**Files:**
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/public/js/bill_tracking.js`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/test_bill_tracking_cancellation.py`

**Interfaces:**
- Consumes: Task 4 Essdee whitelist methods and base YRP button labels.
- Produces: Essdee UI parity while allowing base YRP to remain unchanged.

- [ ] **Step 1: Add failing source-contract tests**

Assert the Essdee handler removes base **Cancel**, removes Assign and invoice-creation actions in cancellation states, calls the new Essdee request/approval methods, and restores final Cancel only for approved HR Users with the existing reason dialog.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Extend the existing serial refresh handler**

Because Frappe executes registered handlers serially, remove the base buttons after its async handler finishes, then add only the state-appropriate Essdee action. Preserve existing YRP Purchase Invoice buttons outside cancellation states.

- [ ] **Step 4: Run tests and JavaScript syntax check**

Run: `node --check essdee_yrp/public/js/bill_tracking.js`

Expected: tests PASS and syntax exit code 0.

### Task 6: Migration Compatibility

**Files:**
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/test_transformers.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/test_planner.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/test_schema.py` if fixture-overlay coverage belongs there

**Interfaces:**
- Consumes: existing `Vendor Bill Tracking -> YRP Bill Tracking` rule and Task 4 Property Setter.
- Produces: regression proof that both statuses are schema-valid and value-preserving.

- [ ] **Step 1: Write failing migration tests**

Transform one source row per new status and assert `form_status` is unchanged. Assert the planner's target `form_status` options include both values and the full plan remains ready with zero issues.

- [ ] **Step 2: Run migration tests and verify RED**

Run from the Frappe 16 app root:
`../../env/bin/python -m unittest essdee_yrp.migration.test_schema essdee_yrp.migration.test_planner essdee_yrp.migration.test_transformers`

- [ ] **Step 3: Make only migration metadata adjustments proven necessary**

The expected implementation is fixture coverage only. Do not add a field map or transformer unless the failing test demonstrates the existing identity mapping is insufficient.

- [ ] **Step 4: Re-run migration tests and verify GREEN**

### Task 7: Integrated Verification and Uncommitted Handoff

**Files:**
- Verify all modified files in both app roots.

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: verified uncommitted working trees and a concise deployment note.

- [ ] **Step 1: Run focused suites on both sites**

Run the complete focused commands from Tasks 1–6 and record exact pass/fail counts.

- [ ] **Step 2: Run broader relevant app tests**

Run the Vendor Bill Tracking/role modules on Frappe 15 and Essdee setup, Bill Tracking, schema, planner, transformer, and runtime acceptance modules on Frappe 16. Report unrelated pre-existing failures by test name.

- [ ] **Step 3: Validate source files**

Run `node --check` for both scripts, Python compilation for changed Python files, JSON parsing for both changed JSON/fixture files, and `git diff --check` in both app repositories.

- [ ] **Step 4: Inspect live metadata after migrate only if explicitly authorized**

Do not run `migrate` as part of implementation. Provide the exact deployment commands and explain that `HR Manager` will be created by the apps' idempotent setup during migration.

- [ ] **Step 5: Review diffs and hand off without committing**

Confirm no unrelated Frappe 16 edits were altered, list every task-owned file, and leave all changes uncommitted.
