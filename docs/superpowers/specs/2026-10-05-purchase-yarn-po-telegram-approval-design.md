# Purchase Yarn PO Telegram Approval Design

## Goal

Require System Manager approval before submitting a Purchase Order containing an item whose parent Item has the exact Item Group `Purchase - Yarn`. Approval must work from Desk and from the existing Process Cost Telegram bot/group in both `production_api` and `essdee_yrp`.

## Constraints

- Add `Pending Approval` to the existing Purchase Order `status` options; add no new Purchase Order fields.
- Reuse the existing Telegram bot, settings, approval request records, and Process Cost group. Add no Telegram channel or Telegram DocType field.
- Apply only to Purchase Orders saved after deployment. Do not backfill existing drafts.
- Non-yarn Purchase Orders retain the current submission flow.
- Keep base `yrp` unchanged; Frappe 16 behavior belongs to `essdee_yrp`.
- Preserve unrelated working-tree changes and do not commit.

## Purchase Order State and Permissions

The yarn check resolves every PO row from Item Variant to Item on Frappe 15, and uses the target row Item on Frappe 16. It matches `Item.item_group == "Purchase - Yarn"` exactly; child groups do not match.

On an ordinary draft save:

- If any row matches, set `status = "Pending Approval"`.
- Otherwise retain the existing Draft status behavior.
- A rejected PO is saved once as Draft using an internal action flag. Its next ordinary edit/save re-evaluates the yarn rule and returns it to Pending Approval.

The standard Submit action is hidden for Pending Approval for non-System-Managers. A user with the exact `System Manager` role may use the standard Submit action directly while the PO is Draft or Pending Approval, even when no Telegram request was sent. Server-side `before_submit` rejects direct submission by every other role. Existing `approved_by` behavior records the approving user.

The Frappe 16 customization ships a Purchase Order `Custom DocPerm` for System Manager so a user holding only that approval role can use the native direct-submit path; base ERPNext and `yrp` remain unchanged.

Any user with Purchase Order create permission can send the Telegram request. Only System Manager can approve or reject from Desk or Telegram.

## Desk Actions

For a saved Pending Approval PO:

- Show **Send Request** to users with Purchase Order create permission when there is no live Telegram request.
- Show **Approve PO** and **Reject PO** only to System Manager.
- Hide the framework Submit action from non-System-Managers; retain it for System Manager.

After a live Telegram request reaches Queued or Pending, ordinary edits and saves are blocked. System Manager may still submit the PO directly; successful submission closes the live request and removes its Telegram action buttons. A Telegram send failure creates an Error request but does not lock the PO, so Send Request can retry.

Approve PO revalidates the persisted row under a database lock, verifies Pending Approval, verifies the exact System Manager role, rechecks the yarn condition, and submits. Reject PO performs the same authorization/state checks, returns the PO to Draft, and unlocks it.

## Telegram Flow

Purchase Order gets an additional route in the existing Telegram Approval Settings. It uses the same group chat ID as the Process Cost route, with:

- trigger field/value: `status` / `Pending Approval`
- actions: `Approve PO` and `Reject PO`
- approve/reject roles: `System Manager`
- field-state targets: approval submits the document; rejection returns it to Draft

Purchase Order routes are manual-send only by code, without adding a route field. The generic document-event sender skips Purchase Order; the Send Request endpoint explicitly invokes the selected PO route. Existing duplicate-request checks prevent repeated live requests.

The message contains:

- PO number
- supplier name
- PO date
- every item row: item, quantity, lot, and rate
- grand total

Telegram callbacks retain the current protections: webhook secret validation, group/message matching, Telegram group membership, Telegram-to-Frappe user mapping, configured role validation, request row locking, and one-time request state. A Purchase Order adapter adds the same hardcoded System Manager and PO-state checks used by Desk.

Desk approval/rejection also closes any live Telegram request and removes its action buttons. Telegram approval/rejection updates the request audit fields and message using the existing mechanism. Stale or repeated callbacks fail without mutating the PO.

## Frappe 15 Implementation

- Extend Purchase Order status metadata.
- Add shared server helpers for yarn detection, live-request locking, approval, rejection, and explicit request sending.
- Harden `before_submit` and draft status calculation.
- Add state-specific form actions and hide Submit.
- Extend the Telegram renderer context and field-state adapter for Purchase Order.
- Keep the existing Telegram DocType schemas unchanged.

## Frappe 16 and Migration

- Add an Essdee-owned Property Setter extending standard Purchase Order status options with `Pending Approval`.
- Add Essdee Purchase Order event handlers and whitelisted actions; keep base `yrp` unchanged.
- Extend the existing Essdee Purchase Order form script with equivalent actions.
- Port/adapt the existing Telegram runtime to the already-migrated `SD YRP Telegram Approval Settings`, `SD YRP Telegram Approval Route`, and `SD YRP Telegram Approval Request` DocTypes.
- Preserve the migrated `Pending Approval` value. The existing Purchase Order transformer already passes unknown status values through; regression tests will prove the target schema accepts it and the value remains unchanged.
- Reuse the migrated Process Cost route's group ID when configuring the additional Purchase Order route. No new channel is created.

## Error Handling

- Missing/disabled Telegram settings or missing PO route: show a clear error and do not lock the PO.
- Telegram API failure: record Error, show the failure, and allow retry.
- Wrong role, stale state, non-System-Manager direct submit, duplicate request, or repeated callback: reject without PO mutation.
- A live request prevents edits until System Manager approves or rejects it.
- Approval revalidates all conditions after acquiring the PO row lock.

## Verification

Tests will cover exact item-group detection, mixed-item POs, non-yarn POs, status setting, System Manager direct submit from Draft/Pending, other-role submit denial, create-permission send access, duplicate sends, lock/unlock behavior, Desk and Telegram approve/reject role checks, message row formatting, Telegram failure retry, stale callbacks, Frappe 16 parity, target status metadata, and migration value preservation. JavaScript syntax/behavior, Python compilation, JSON parsing, and scoped diffs will also be checked.
