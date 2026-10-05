# Purchase Yarn PO Telegram Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require System Manager approval before a Purchase Order containing exact Item Group `Purchase - Yarn` can be submitted, with equivalent Desk and Telegram approve/reject flows in Frappe 15 and Frappe 16.

**Architecture:** Both apps own a server-authoritative Purchase Order approval module attached through document events, leaving their existing Purchase Order controllers and base `yrp` unchanged. Frappe 15 extends the existing Telegram approval engine; Frappe 16 ports that runtime against the already-migrated `SD YRP Telegram Approval *` DocTypes. A live Telegram Approval Request is the lock record, so no Purchase Order or Telegram schema fields are added.

**Tech Stack:** Frappe 15/16, Python, JavaScript, DocType JSON/Property Setter fixtures, Telegram Bot API, `unittest`/Frappe test runner, Node VM behavior tests.

**Spec:** `docs/superpowers/specs/2026-10-05-purchase-yarn-po-telegram-approval-design.md`

## Global Constraints

- Match `Item.item_group == "Purchase - Yarn"` exactly; child groups and similar names do not match.
- Add only `Pending Approval` to existing Purchase Order status options; add no Purchase Order or Telegram fields.
- Reuse the Process Cost bot and group through an additional route in the existing Telegram settings.
- Do not backfill existing draft Purchase Orders.
- Only users with Purchase Order create permission can send; only exact `System Manager` role holders can approve or reject.
- Keep base Frappe 16 `yrp` unchanged.
- Preserve unrelated dirty changes in both apps, especially `essdee_yrp/hooks.py`, migration tests/transformers, and the previous Vendor Bill work.
- Do not run migrate, configure a live webhook, call Telegram, commit, push, or create a PR.

## Review Focus

- Direct framework/RPC submission of a yarn PO must fail for non-System-Managers; System Manager may submit directly from Draft or Pending Approval without first sending a request.
- One exact yarn row among mixed items must trigger approval, while child-group or similarly named rows must not.
- Telegram Error requests must allow retry; Queued/Pending requests must prevent edits and duplicate sends.
- Stale, repeated, wrong-group, unmapped-user, and non-System-Manager callbacks must leave both PO and request auditable and unchanged.
- Frappe 16 migration must preserve `status = Pending Approval` while deriving `yrp_fulfillment_status = Draft` and keeping the planner ready.

---

### Task 1: Frappe 15 Purchase Order Approval State Machine

**Files:**
- Create: `production_api/purchase_order_approval.py`
- Create: `production_api/test_purchase_order_approval.py`
- Modify: `production_api/production_api/doctype/purchase_order/purchase_order.json`
- Modify: `production_api/hooks.py`

**Interfaces:**
- Produces: `requires_yarn_approval(doc) -> bool`, `apply_draft_approval_status(doc, method=None) -> None`, `validate_approval_submit(doc, method=None) -> None`.
- Produces: whitelisted `approve_purchase_order(name: str)`, `reject_purchase_order(name: str)` and shared exact constants.
- Consumes: Item Variant → Item → exact Item Group lookup and the existing `approved_by` behavior in the Purchase Order controller.

- [ ] **Step 1: Write failing metadata and item-group behavior tests**

Assert `Pending Approval` occurs once in the status options; mixed rows with one exact `Purchase - Yarn` Item trigger; empty, child, and similarly named groups do not; a saved draft receives Pending Approval; non-yarn remains Draft.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `../../env/bin/python -m unittest production_api.test_purchase_order_approval.TestPurchaseOrderApprovalState`

Expected: failure because the module/status behavior does not exist.

- [ ] **Step 3: Implement metadata, exact yarn detection, and before-save event hook**

Use batched Item Variant/Item lookups, change only draft documents, and skip the automatic Pending transition only under the internal rejection flag.

- [ ] **Step 4: Run the focused state tests and verify GREEN**

- [ ] **Step 5: Write failing authorization and transition tests**

Cover direct submit denial for non-System-Managers, direct submit success for System Manager from Draft/Pending, wrong-role Desk approve/reject, row locking, out-of-order/repeated actions, approved submission reaching docstatus 1/Ordered with `approved_by`, and rejection returning Draft.

- [ ] **Step 6: Run transition tests and verify RED**

- [ ] **Step 7: Implement locked Desk approve/reject and before-submit guard**

Both actions reload the PO under `for_update=True`, require draft + Pending Approval + exact yarn condition + System Manager, and set a narrowly scoped action flag. Register `before_submit` in hooks, allowing standard direct submit for System Manager only.

- [ ] **Step 8: Run all Task 1 tests and verify GREEN**

Expected: all state, role, and bypass tests pass.

### Task 2: Frappe 15 Manual Telegram Request and PO Adapter

**Files:**
- Modify: `production_api/purchase_order_approval.py`
- Modify: `production_api/telegram_approval/service.py`
- Modify: `production_api/telegram_approval/renderers.py`
- Modify: `production_api/telegram_approval/adapters.py`
- Modify: `production_api/telegram_approval/test_telegram_approval.py`
- Modify: `production_api/production_api/doctype/telegram_approval_settings/telegram_approval_settings.py`
- Modify: `production_api/hooks.py`
- Test: `production_api/test_purchase_order_approval.py`

**Interfaces:**
- Consumes: Task 1 approval/rejection functions and constants.
- Produces: whitelisted `send_purchase_order_request(name: str)`, idempotent `ensure_purchase_order_approval_route()`, normalized `purchase_order_items` message context, and Purchase Order field-state action handler.
- Produces: `get_live_request(name)`, explicit route lookup/send, and request-finalization helpers used by Desk and Telegram.

- [ ] **Step 1: Write failing message and manual-send tests**

Assert the rendered message includes PO number, supplier, PO date, every item/quantity/lot/rate, and grand total. Assert the generic document event does not auto-send a Purchase Order route, while explicit Send Request selects the PO route.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `../../env/bin/python -m unittest production_api.telegram_approval.test_telegram_approval production_api.test_purchase_order_approval`

Expected: missing PO context/send API failures.

- [ ] **Step 3: Add PO message context, manual route selection, and route setup**

Create an additional Field State route using the first enabled Process Cost route's existing `group_chat_id`, `status/Pending Approval`, `Approve PO/Reject PO`, `Ordered/Draft`, and System Manager roles. Wire setup through `after_install` and `after_migrate`, and retry idempotent setup from Send Request so a Process Cost route configured later is picked up; no-op if settings or a Process Cost route is unavailable.

- [ ] **Step 4: Run message/manual-send tests and verify GREEN**

- [ ] **Step 5: Write failing request lifecycle tests**

Cover create-permission and read-permission checks, missing/disabled settings, missing route, duplicate live request reuse, successful Pending lock, Error retry, edit blocking for Queued/Pending only, and Desk action finalization of a live message.

- [ ] **Step 6: Run lifecycle tests and verify RED**

- [ ] **Step 7: Implement explicit synchronous send and request-derived locking**

Call the existing Telegram client only from Send Request; lock only Queued/Pending; preserve Error for audit and allow another request. Ensure Desk approve/reject closes the live request and removes Telegram buttons.

- [ ] **Step 8: Write failing Telegram action tests**

Assert a mapped System Manager callback approves/submits or rejects/unlocks; a mapped non-manager, stale/repeated request, wrong status, and direct target-value manipulation fail without PO mutation.

- [ ] **Step 9: Implement the Purchase Order field-state adapter**

Keep generic configured-role validation, then delegate to Task 1's server-authoritative locked actions under the mapped Frappe user.

- [ ] **Step 10: Run all Task 2 tests and verify GREEN**

### Task 3: Frappe 15 Purchase Order Form Actions

**Files:**
- Modify: `production_api/production_api/doctype/purchase_order/purchase_order.js`
- Create: `production_api/production_api/doctype/purchase_order/test_purchase_order_approval_ui.js`

**Interfaces:**
- Consumes: Task 1 Desk endpoints and Task 2 Send Request/live-request status response.
- Produces: state-specific **Send Request**, **Approve PO**, and **Reject PO** actions plus framework Submit suppression.

- [ ] **Step 1: Write failing executable UI behavior tests**

Load the real form script in a Node VM. Assert Pending Approval hides primary Submit from non-System-Managers but retains it for System Manager; a create-permitted user sees Send Request only without a live request; only System Manager sees Approve PO/Reject PO; callbacks invoke the exact APIs and reload. Assert ordinary Draft remains unchanged.

- [ ] **Step 2: Run the Node test and verify RED**

Run: `node production_api/production_api/doctype/purchase_order/test_purchase_order_approval_ui.js`

Expected: missing actions and visible Submit.

- [ ] **Step 3: Implement form predicates and actions**

Use `frappe.perm.has_perm("Purchase Order", 0, "create")`, a read-only server status call for the live request, confirmations for approve/reject, and no client-only authorization assumptions.

- [ ] **Step 4: Run behavior and syntax tests and verify GREEN**

Run: `node production_api/production_api/doctype/purchase_order/test_purchase_order_approval_ui.js && node --check production_api/production_api/doctype/purchase_order/purchase_order.js`

Expected: PASS and syntax exit 0.

### Task 4: Frappe 16 Essdee Purchase Order Parity

**Files:**
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/purchase_order_approval.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/test_purchase_order_approval.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/hooks.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/fixtures/property_setter.json`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/fixtures/custom_docperm.json`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/public/js/purchase_order.js`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/public/js/test_purchase_order_approval.js`

**Interfaces:**
- Produces: Frappe 16 equivalents of every Task 1 state/Desk API, operating only when `is_yrp_managed` is true.
- Produces: Essdee-owned Purchase Order status Property Setter, System Manager submit permission, and equivalent Desk actions.
- Consumes: standard Purchase Order rows (`item_code`) and base YRP status lifecycle without modifying `yrp`.

- [ ] **Step 1: Write failing metadata, state-machine, and mixed-row tests**

Mirror Task 1 and assert non-YRP standard Purchase Orders are untouched. Assert target status options include Pending Approval once.

- [ ] **Step 2: Run tests and verify RED**

Run: `/home/anas/pilot/benches/frappe-16/env/bin/python -m unittest essdee_yrp.test_purchase_order_approval`

- [ ] **Step 3: Add the Property Setter and event-driven state machine**

Register before-save and before-submit event handlers alongside the existing linked-lot handler. Preserve base YRP's `yrp_fulfillment_status = Draft` while setting only standard `status = Pending Approval`.

- [ ] **Step 4: Run server tests and verify GREEN**

- [ ] **Step 5: Write failing Essdee UI behavior tests**

Assert the Essdee handler removes/hides base Submit in Pending Approval and adds the same role/permission-specific actions using Essdee routes.

- [ ] **Step 6: Run UI test and verify RED**

- [ ] **Step 7: Implement Essdee form parity**

- [ ] **Step 8: Run server, UI, and syntax tests and verify GREEN**

### Task 5: Frappe 16 Telegram Runtime and PO Actions

**Files:**
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/__init__.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/client.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/service.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/renderers.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/adapters.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/api.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/telegram_approval/test_telegram_approval.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/essdee_yrp/doctype/sd_yrp_telegram_approval_settings/sd_yrp_telegram_approval_settings.py`
- Create: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/essdee_yrp/doctype/sd_yrp_telegram_approval_settings/sd_yrp_telegram_approval_settings.js`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/hooks.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/setup.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/purchase_order_approval.py`

**Interfaces:**
- Consumes: Task 4 Essdee state actions and the existing `SD YRP Telegram Approval Settings/Route/Request` schemas.
- Produces: secure target webhook, client, request service, renderer, callback adapter, manual PO route, and Process Cost-compatible generic Workflow/Field State support.

- [ ] **Step 1: Write failing port contract tests**

Cover SD YRP DocType names, Essdee webhook URL, secret comparison, callback row lock, group/message verification, membership, mapped-user lookup, one-time state, sanitized API errors, and settings route validation.

- [ ] **Step 2: Run tests and verify RED**

Run: `/home/anas/pilot/benches/frappe-16/env/bin/python -m unittest essdee_yrp.telegram_approval.test_telegram_approval essdee_yrp.test_purchase_order_approval`

- [ ] **Step 3: Port the runtime with namespaced constants**

Adapt the proven Frappe 15 modules rather than importing `production_api`; preserve security checks and generic Process Cost workflow capability. Register global document events and settings UI against the Essdee webhook. The target PO adapter accepts the migrated source approval marker `Ordered` but derives the actual submitted target status through the YRP controller (`To Receive`).

- [ ] **Step 4: Run port tests and verify GREEN**

- [ ] **Step 5: Write failing Essdee PO message/lifecycle/action tests**

Mirror Task 2 for target item fields and SD YRP request records, including send failure retry, locking, Desk finalization, Telegram approve/reject, and exact message rows.

- [ ] **Step 6: Run PO Telegram tests and verify RED**

- [ ] **Step 7: Implement target route setup and PO adapter**

Call route setup idempotently from install/migrate after the migrated settings exist. Reuse the Process Cost route group ID and never create a channel.

- [ ] **Step 8: Run all Task 5 tests and verify GREEN**

### Task 6: Migration Compatibility

**Files:**
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/transformers.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/test_transformers.py`
- Modify: `/home/anas/pilot/benches/frappe-16/apps/essdee_yrp/essdee_yrp/migration/test_planner.py`

**Interfaces:**
- Consumes: Task 4 status Property Setter and existing Purchase Order mapping.
- Produces: `Pending Approval` status preservation with target fulfillment Draft and planner-ready schema proof.

- [ ] **Step 1: Write failing migration regression tests**

Transform a draft Purchase Order with `status = Pending Approval`; assert target `status` is unchanged, `yrp_fulfillment_status == "Draft"`, the Purchase Order route's group/actions survive settings migration, and target status options include Pending Approval with zero plan issues.

- [ ] **Step 2: Run migration tests and verify RED**

Run: `/home/anas/pilot/benches/frappe-16/env/bin/python -m unittest essdee_yrp.migration.test_schema essdee_yrp.migration.test_planner essdee_yrp.migration.test_transformers`

- [ ] **Step 3: Adjust only Purchase Order derivation proven necessary**

Special-case Pending Approval as an approval state: preserve standard status while deriving Draft fulfillment. Do not change unrelated mappings or user-owned transformer edits.

- [ ] **Step 4: Re-run migration tests and verify GREEN**

### Task 7: Integrated Verification and Uncommitted Handoff

**Files:**
- Verify every modified path in both repositories.

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: tested, uncommitted working trees and deployment/cutover notes.

- [ ] **Step 1: Run complete focused Python suites**

Run all new Purchase Order and Telegram modules plus existing Telegram tests on Frappe 15; run all new Essdee modules and migration suites on Frappe 16. Use the Frappe 16 test site for the focused module when available; report pre-existing bootstrap failures separately.

- [ ] **Step 2: Run JavaScript behavior and syntax checks**

Run both Node VM tests and `node --check` on both Purchase Order scripts and the Essdee Telegram Settings script.

- [ ] **Step 3: Validate Python/JSON and scoped diffs**

Compile changed Python, parse changed JSON, run scoped `git diff --check`, confirm base `yrp` is untouched, and distinguish pre-existing dirty lines from this plan's changes.

- [ ] **Step 4: Perform whole-change review**

Review role/state bypasses, route security, settings cutover, error retry, locks, and migration behavior. Fix Critical/Important findings with RED→GREEN tests; ledger deferred minors.

- [ ] **Step 5: Hand off without deployment or commit**

State that Telegram supports only one active webhook per bot: after target cutover, run Configure Webhook on the active site. Do not migrate or alter live Telegram settings during implementation.
